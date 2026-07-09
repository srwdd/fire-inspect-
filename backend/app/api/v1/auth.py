import hashlib, hmac, json, os, sqlite3, time
from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

router = APIRouter()
SECRET = os.environ.get('JWT_SECRET', 'fire-inspect-secret-key-2026')
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'fire_inspect.db')

def _db():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row; return conn

def _hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def _make_token(user_id, role, org_id):
    import base64
    h = json.dumps({'alg': 'HS256', 'typ': 'JWT'})
    p = json.dumps({'uid': user_id, 'role': role, 'oid': org_id or 0, 'exp': int(time.time()) + 86400 * 7})
    msg = base64.urlsafe_b64encode(h.encode()).decode().rstrip('=') + '.' + base64.urlsafe_b64encode(p.encode()).decode().rstrip('=')
    sig = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return msg + '.' + sig

def _decode_token(token):
    try:
        parts = token.split('.')
        if len(parts) != 3: return None
        h, p, sig = parts
        msg = h + '.' + p
        expected = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if sig != expected: return None
        import base64
        pad = 4 - len(p) % 4
        if pad < 4: p += '=' * pad
        return json.loads(base64.urlsafe_b64decode(p.encode()))
    except: return None


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


@router.post('/login')
def login(req: LoginRequest):
    conn = _db()
    row = conn.execute('SELECT * FROM users WHERE username = ? AND active = 1', (req.username,)).fetchone()
    conn.close()
    if not row or row['password_hash'] != _hash_pw(req.password):
        raise HTTPException(401, '用户名或密码错误')
    org_name = ''
    if row['org_id']:
        c2 = _db()
        o = c2.execute('SELECT name FROM organizations WHERE id = ?', (row['org_id'],)).fetchone()
        c2.close()
        if o: org_name = o['name']
    token = _make_token(row['id'], row['role'], row['org_id'] or 0)
    return {'code': 0, 'data': {
        'token': token,
        'user': {'id': row['id'], 'username': row['username'], 'role': row['role'],
                 'display_name': row['display_name'], 'org_id': row['org_id'] or 0, 'org_name': org_name}
    }}

@router.get('/me')
def me(current_user: dict = None):
    try:
        current_user = None
        # me is called with Depends(get_current_user) - handled in routes
    except: pass
    return {'code': 0, 'data': {'ok': True}}

@router.get('/organizations')
def list_orgs():
    conn = _db()
    rows = conn.execute('SELECT * FROM organizations WHERE active = 1 ORDER BY id').fetchall()
    conn.close()
    return {'code': 0, 'data': [{'id': r['id'], 'name': r['name'], 'short_name': r['short_name']} for r in rows]}

@router.post('/users')
def create_user(data: UserCreate):
    conn = _db()
    # 检查用户名是否已存在
    existing = conn.execute('SELECT id FROM users WHERE username = ?', (data.username,)).fetchone()
    if existing:
        conn.close()
        from fastapi import HTTPException
        raise HTTPException(400, f'用户名 {data.username} 已存在')
    conn.execute('INSERT INTO users (username, password_hash, role, display_name, org_id) VALUES (?,?,?,?,?)',
                 (data.username, _hash_pw(data.password), data.role, data.display_name, data.org_id))
    conn.commit(); conn.close()
    return {'code': 0, 'msg': f'用户 {data.display_name} 创建成功'}

@router.get('/users')
def list_users(org_id: int = 0):
    conn = _db()
    if org_id: rows = conn.execute('SELECT * FROM users WHERE active = 1 AND org_id = ?', (org_id,)).fetchall()
    else: rows = conn.execute('SELECT * FROM users WHERE active = 1').fetchall()
    conn.close()
    result = []
    for r in rows:
        org_name = ''
        if r['org_id']:
            c2 = _db()
            o = c2.execute('SELECT name FROM organizations WHERE id = ?', (r['org_id'],)).fetchone()
            c2.close()
            if o: org_name = o['name']
        result.append({'id': r['id'], 'username': r['username'], 'role': r['role'],
            'display_name': r['display_name'], 'org_id': r['org_id'] or 0, 'org_name': org_name})
    return {'code': 0, 'data': result}
