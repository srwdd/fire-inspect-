"""
业主自查 API — 无需登录，通过唯一 code 访问
"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.core.checklist_engine import checklist_engine
from app.db.storage import (
    get_owner_submission, create_owner_submission,
    update_owner_item, submit_owner, list_owner_submissions,
    update_owner_status, update_owner_return
)

router = APIRouter()


class OwnerSubmitItem(BaseModel):
    item_index: int
    result: str = ""
    note: str = ""


@router.get("/check/{code}")
def get_owner_check(code: str):
    """业主通过 code 获取自查清单"""
    sub = get_owner_submission(code)
    if not sub:
        raise HTTPException(404, "链接无效或已过期")
    items = checklist_engine.get_check_items(sub["venue_type"], "preopen")
    return {
        "code": 0,
        "data": {
            "code": sub["code"],
            "venue_type": sub["venue_type"],
            "venue_name": sub["venue_name"],
            "venue_address": sub["venue_address"],
            "contact_name": sub.get("contact_name", ""),
            "contact_phone": sub.get("contact_phone", ""),
            "status": sub["status"],
            "return_reason": sub.get("return_reason", ""),
            "total_items": len(items),
            "submitted_items": sub.get("items", []),
            "items": items,
        }
    }


@router.post("/check/{code}/item")
async def save_owner_item(
    code: str,
    item_index: int = Form(...),
    result: str = Form(""),
    note: str = Form(""),
    files: list[UploadFile] = File(default=[])
):
    """业主保存单项自查结果（含照片）"""
    photos = []
    for f in (files or []):
        if f.filename:
            import base64
            content = await f.read()
            photos.append({
                "name": f.filename,
                "data": base64.b64encode(content).decode("utf-8"),
                "type": f.content_type or "image/jpeg"
            })

    data = {"result": result, "note": note, "photos": photos, "saved_at": datetime.now().isoformat()}
    update_owner_item(code, item_index, data)
    return {"code": 0, "msg": "已保存"}


@router.post("/check/{code}/submit")
def submit_owner_check(code: str):
    """业主提交全部自查"""
    submit_owner(code)
    return {"code": 0, "msg": "提交成功，消防监督员将进行核查"}


# ── 消防员端 ──

@router.delete("/submissions/{code}")
def delete_owner_submission(code: str):
    """消防员删除业主提交"""
    from app.db.storage import _connect
    with _connect() as conn:
        conn.execute("DELETE FROM owner_submissions WHERE code=?",(code,))
        conn.commit()
    return {"code": 0, "msg": "已删除"}

@router.get("/submissions")
def get_owner_submissions(org_id: int = 0):
    """消防员查看所有业主提交"""
    subs = list_owner_submissions(org_id)
    return {"code": 0, "data": [{
        "code": s["code"],
        "venue_name": s.get("venue_name", ""),
        "venue_type": s.get("venue_type", ""),
        "venue_address": s.get("venue_address", ""),
        "contact_name": s.get("contact_name", ""),
        "contact_phone": s.get("contact_phone", ""),
        "status": s["status"],
        "created_at": s["created_at"],
        "submitted_at": s.get("submitted_at", ""),
        "item_count": len(json.loads(s.get("items_json", "[]")) if isinstance(s.get("items_json"), str) else s.get("items_json", [])),
    } for s in subs]}


@router.get("/submissions/{code}")
def get_owner_submission_detail(code: str):
    """消防员查看某业主提交详情"""
    sub = get_owner_submission(code)
    if not sub:
        raise HTTPException(404, "未找到该提交")
    items = checklist_engine.get_check_items(sub["venue_type"], "preopen")
    # Decode items_json for photos
    import json as _json
    sub_items = _json.loads(sub.get("items_json", "[]")) if isinstance(sub.get("items_json"), str) else sub.get("items", [])
    return {
        "code": 0,
        "data": {
            "submission": sub,
            "checklist": items,
            "owner_items": sub_items,
        }
    }


@router.post("/submissions/{code}/review")
def review_owner_submission(code: str, status: str = "reviewed", reason: str = ""):
    """消防员审核（通过/退回）"""
    if status == "returned":
        update_owner_return(code, reason)
    else:
        update_owner_status(code, status)
    return {"code": 0, "msg": "操作成功"}


@router.post("/submissions/{code}/return")
def return_owner_submission(code: str, reason: str = ""):
    """消防员退回业主提交（需修改）"""
    update_owner_return(code, reason)
    return {"code": 0, "msg": "已退回"}


@router.post("/check/{code}/resubmit")
def resubmit_owner_check(code: str):
    """业主重新提交"""
    submit_owner(code)
    return {"code": 0, "msg": "已重新提交"}


@router.post("/create-link")
def create_owner_link(
    venue_type: str = "hotel",
    venue_name: str = "",
    venue_address: str = "",
    inspector_id: int = 0,
    org_id: int = 0
):
    """消防员生成业主自查链接"""
    import secrets
    code = "OWNER-" + secrets.token_hex(4).upper()
    create_owner_submission(code, venue_type, venue_name, venue_address, inspector_id, org_id)
    return {
        "code": 0,
        "data": {
            "code": code,
            "url": f"/inspect/web/owner.html?code={code}",
            "full_url": f"https://ai-bang.top/inspect/web/owner.html?code={code}"
        }
    }
