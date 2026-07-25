import hashlib, hmac, json, logging, os, secrets, sqlite3, time
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends, Request
from pydantic import BaseModel, Field
from app.dependencies import get_current_user
from app.core.rate_limiter import login_limiter

logger = logging.getLogger('fire_inspect.auth')

router = APIRouter()

# ── JWT 密钥 ─────────────────────────────────────
# 生产环境必须通过 JWT_SECRET 环境变量（或 .env）配置持久密钥。
# 未配置时生成随机密钥：服务重启后所有 token 失效，避免硬编码密钥被伪造。
_SECRET_ENV = os.environ.get('JWT_SECRET', '').strip()
if _SECRET_ENV:
    SECRET = _SECRET_ENV
else:
    SECRET = secrets.token_hex(32)
    logger.warning('JWT_SECRET 未配置，已生成随机密钥；重启后所有 token 将失效。生产环境请在 .env 中设置 JWT_SECRET。')

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'fire_inspect.db')

# 允许的角色集合（与 seed_orgs.py / ws.py 保持一致）
ALLOWED_ROLES = ('admin', 'chief', 'lead', 'assist')

def _db():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row; return conn

# ── 密码哈希：PBKDF2-HMAC-SHA256（标准库实现，无新依赖）──────────────
# 格式: pbkdf2$<iterations>$<salt_hex>$<digest_hex>
# 兼容旧的无盐 SHA-256 哈希，登录成功时透明升级。
_PBKDF2_ITERATIONS = 200_000

def _hash_pw(pw: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return f'pbkdf2${_PBKDF2_ITERATIONS}${salt}${digest.hex()}'

def _verify_pw(pw: str, stored: str) -> bool:
    """校验密码。支持 PBKDF2 新格式与旧版无盐 SHA-256。"""
    if not stored:
        return False
    if stored.startswith('pbkdf2$'):
        try:
            _, iters, salt, digest = stored.split('$')
            calc = hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), int(iters)).hex()
            return hmac.compare_digest(calc, digest)
        except Exception:
            return False
    # 旧格式：无盐 SHA-256
    return hmac.compare_digest(hashlib.sha256(pw.encode()).hexdigest(), stored)

def _make_token(user_id, role, org_id):
    import base64
    h = json.dumps({'alg': 'HS256', 'typ': 'JWT'})
    p = json.dumps({'uid': user_id, 'role': role, 'oid': org_id or 0, 'exp': int(time.time()) + 86400 * 7})
    msg = base64.urlsafe_b64encode(h.encode()).decode().rstrip('=') + '.' + base64.urlsafe_b64encode(p.encode()).decode().rstrip('=')
    sig = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return msg + '.' + sig

def _decode_token(token):
    """验签 + 校验 exp 过期时间。任何一步失败返回 None。"""
    try:
        parts = token.split('.')
        if len(parts) != 3: return None
        h, p, sig = parts
        msg = h + '.' + p
        expected = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected): return None
        import base64
        pad = 4 - len(p) % 4
        if pad < 4: p += '=' * pad
        payload = json.loads(base64.urlsafe_b64decode(p.encode()))
        if payload.get('exp', 0) < time.time():
            return None
        return payload
    except Exception:
        return None


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)

class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=4, max_length=100)
    role: str = Field(default='assist')
    display_name: str = Field(..., min_length=1, max_length=50)
    org_id: int = Field(default=0)

async def get_current_user(authorization: str = Header(None)):
    if not authorization: raise HTTPException(401, '请先登录')
    token = authorization.replace('Bearer ', '')
    payload = _decode_token(token)
    if not payload: raise HTTPException(401, '登录已过期')
    return payload

def _org_name(org_id: int) -> str:
    if not org_id:
        return ''
    conn = _db()
    row = conn.execute('SELECT name FROM organizations WHERE id = ?', (org_id,)).fetchone()
    conn.close()
    return row['name'] if row else ''


@router.post('/login')
def login(req: LoginRequest, request: Request):
    # Rate limiting: 5 failed attempts per minute -> 15 min block
    client_ip = request.client.host if request.client else 'unknown'
    blocked, remaining = login_limiter.is_blocked(client_ip)
    if blocked:
        raise HTTPException(429, {'code': 1, 'msg': f'登录过于频繁，请 {remaining} 秒后重试'})
    blocked, remaining = login_limiter.is_blocked(req.username)
    if blocked:
        raise HTTPException(429, {'code': 1, 'msg': f'该账号登录过于频繁，请 {remaining} 秒后重试'})

    conn = _db()
    row = conn.execute('SELECT * FROM users WHERE username = ? AND active = 1', (req.username,)).fetchone()
    conn.close()
    if not row or not _verify_pw(req.password, row['password_hash']):
        login_limiter.record_attempt(client_ip)
        login_limiter.record_attempt(req.username)
        raise HTTPException(401, '用户名或密码错误')
    # 旧格式密码哈希透明升级为 PBKDF2
    if not row['password_hash'].startswith('pbkdf2$'):
        try:
            conn = _db()
            conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (_hash_pw(req.password), row['id']))
            conn.commit(); conn.close()
        except Exception:
            logger.warning('密码哈希升级失败 uid=%s', row['id'])
    org_name = _org_name(row['org_id'])
    login_limiter.reset(client_ip)
    login_limiter.reset(req.username)
    token = _make_token(row['id'], row['role'], row['org_id'] or 0)
    return {'code': 0, 'data': {
        'token': token,
        'user': {'id': row['id'], 'username': row['username'], 'role': row['role'],
                 'display_name': row['display_name'], 'org_id': row['org_id'] or 0, 'org_name': org_name}
    }}

@router.get('/me')
def me(current_user: dict = Depends(get_current_user)):
    """返回当前登录用户信息（从数据库读取，token 里只有 uid/role/oid）。"""
    conn = _db()
    row = conn.execute(
        'SELECT id, username, role, display_name, org_id FROM users WHERE id = ? AND active = 1',
        (current_user.get('uid', 0),)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(401, '用户不存在或已停用')
    return {'code': 0, 'data': {'id': row['id'], 'username': row['username'],
            'role': row['role'], 'display_name': row['display_name'],
            'org_id': row['org_id'] or 0, 'org_name': _org_name(row['org_id'])}}

@router.get('/organizations')
def list_orgs():
    conn = _db()
    rows = conn.execute('SELECT * FROM organizations WHERE active = 1 ORDER BY id').fetchall()
    conn.close()
    return {'code': 0, 'data': [{'id': r['id'], 'name': r['name'], 'short_name': r['short_name']} for r in rows]}

@router.post('/users')
def create_user(data: UserCreate, current_user: dict = Depends(get_current_user)):
    """创建用户（仅管理员）。"""
    if current_user.get('role') != 'admin':
        raise HTTPException(403, '仅管理员可创建用户')
    if data.role not in ALLOWED_ROLES:
        raise HTTPException(400, f'无效角色: {data.role}，允许值: {", ".join(ALLOWED_ROLES)}')
    conn = _db()
    # 检查用户名是否已存在
    existing = conn.execute('SELECT id FROM users WHERE username = ?', (data.username,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, f'用户名 {data.username} 已存在')
    conn.execute('INSERT INTO users (username, password_hash, role, display_name, org_id) VALUES (?,?,?,?,?)',
                 (data.username, _hash_pw(data.password), data.role, data.display_name, data.org_id))
    conn.commit(); conn.close()
    return {'code': 0, 'msg': f'用户 {data.display_name} 创建成功'}

@router.get('/users')
def list_users(org_id: int = 0, current_user: dict = Depends(get_current_user)):
    """用户列表（需登录）。不返回密码哈希。"""
    conn = _db()
    if org_id: rows = conn.execute('SELECT * FROM users WHERE active = 1 AND org_id = ?', (org_id,)).fetchall()
    else: rows = conn.execute('SELECT * FROM users WHERE active = 1').fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({'id': r['id'], 'username': r['username'], 'role': r['role'],
            'display_name': r['display_name'], 'org_id': r['org_id'] or 0, 'org_name': _org_name(r['org_id'])})
    return {'code': 0, 'data': result}
