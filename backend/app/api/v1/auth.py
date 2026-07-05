"""Authentication endpoints — JWT login, user management."""
import hashlib, hmac, json, os, time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.dependencies import get_current_user

router = APIRouter()
SECRET = os.environ.get("JWT_SECRET", "fire-inspect-secret-key-2026")

def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _make_token(user_id: int, role: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"uid": user_id, "role": role, "exp": int(time.time()) + 86400 * 7}
    h = json.dumps(header)
    p = json.dumps(payload)
    import base64
    msg = base64.urlsafe_b64encode(h.encode()).decode().rstrip("=") + "." + base64.urlsafe_b64encode(p.encode()).decode().rstrip("=")
    sig = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return msg + "." + sig

def _decode_token(token: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3: return None
        h, p, sig = parts
        msg = h + "." + p
        expected = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if sig != expected: return None
        import base64
        pad = 4 - len(p) % 4
        if pad < 4: p += "=" * pad
        payload = json.loads(base64.urlsafe_b64decode(p.encode()))
        if payload.get("exp", 0) < time.time(): return None
        return payload
    except: return None


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)

class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=4, max_length=100)
    role: str = Field(default="assist", pattern="^(admin|chief|lead|assist)$")
    display_name: str = Field(..., min_length=1, max_length=50)
    unit: str = Field(default="")

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username, User.active == True).first()
    if not user or user.password_hash != _hash_pw(req.password):
        raise HTTPException(401, "用户名或密码错误")
    token = _make_token(user.id, user.role)
    return {"code": 0, "data": {
        "token": token, "user": {"id": user.id, "username": user.username,
        "role": user.role, "display_name": user.display_name, "unit": user.unit}
    }}

@router.get("/me")
def me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user["uid"]).first()
    if not user: raise HTTPException(404, "用户不存在")
    return {"code": 0, "data": {"id": user.id, "username": user.username,
        "role": user.role, "display_name": user.display_name, "unit": user.unit}}

@router.post("/users")
def create_user(req: UserCreate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user["role"] != "admin":
        raise HTTPException(403, "仅管理员可创建用户")
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(400, "用户名已存在")
    user = User(username=req.username, password_hash=_hash_pw(req.password),
                role=req.role, display_name=req.display_name, unit=req.unit)
    db.add(user); db.commit()
    return {"code": 0, "data": {"id": user.id, "username": user.username}}

@router.get("/users")
def list_users(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user["role"] not in ("admin", "chief"):
        raise HTTPException(403, "权限不足")
    users = db.query(User).filter(User.active == True).all()
    return {"code": 0, "data": [{"id": u.id, "username": u.username,
        "role": u.role, "display_name": u.display_name, "unit": u.unit} for u in users]}
