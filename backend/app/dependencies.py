"""FastAPI 共享依赖 — 认证、权限控制"""
import os as _os
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request


async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> bool:
    """验证 API Key（如果环境变量中设置了 API_KEY）。

    未设置 API_KEY 时跳过验证（本地开发模式）。
    已设置时，请求必须携带匹配的 X-API-Key header。

    注意：业务路由应优先使用 get_current_user（JWT）认证，
    本依赖仅保留给未来的开放 API 场景。
    """
    expected = _os.environ.get("API_KEY", "").strip()
    if not expected:
        # 本地开发模式 — 无 API Key 要求
        return True
    if x_api_key == expected:
        return True
    raise HTTPException(status_code=401, detail="无效的 API Key — 请在请求头中设置 X-API-Key")

async def get_current_user(authorization: str = Header(None)) -> dict:
    """JWT authentication middleware. Returns user payload or raises 401."""
    from app.api.v1.auth import _decode_token
    if not authorization:
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization.replace("Bearer ", "")
    payload = _decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return payload


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """要求管理员角色，否则 403。"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
