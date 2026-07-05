"""FastAPI 共享依赖 — 认证、权限控制"""
import os as _os
from typing import Optional

from fastapi import Header, HTTPException, Request


async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> bool:
    """验证 API Key（如果环境变量中设置了 API_KEY）。

    未设置 API_KEY 时跳过验证（本地开发模式）。
    已设置时，请求必须携带匹配的 X-API-Key header。
    """
    expected = _os.environ.get("API_KEY", "").strip()
    if not expected:
        # 本地开发模式 — 无 API Key 要求
        return True
    if x_api_key == expected:
        return True
    raise HTTPException(status_code=401, detail="无效的 API Key — 请在请求头中设置 X-API-Key")
