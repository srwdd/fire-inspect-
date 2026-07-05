"""简易审批流 — 监督员→队长→大队 三级 (Phase P3)"""
from datetime import datetime
from typing import Any, Dict

from app.db.storage import get_inspection, update_inspection_status

VALID_TRANSITIONS = {
    "in_progress": ["submitted"],
    "submitted": ["reviewed", "rejected"],
    "reviewed": ["approved", "rejected"],
    "rejected": ["submitted"],  # 驳回后可重新提交
}


def transition(inspection_id: str, new_status: str, reviewer: str = "", comment: str = "") -> Dict[str, Any]:
    """状态机: 校验并执行状态流转"""
    insp = get_inspection(inspection_id)
    if not insp:
        return {"ok": False, "error": "检查记录不存在"}

    current = insp.get("status", "in_progress")
    allowed = VALID_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        return {"ok": False, "error": f"不允许从 {current} 流转到 {new_status}，允许: {allowed}"}

    # 写入日志
    log = insp.get("_workflow_log") or []
    log.append({
        "from": current,
        "to": new_status,
        "reviewer": reviewer,
        "comment": comment,
        "timestamp": datetime.now().isoformat(),
    })

    update_inspection_status(inspection_id, new_status)

    return {
        "ok": True,
        "from_status": current,
        "to_status": new_status,
        "workflow_log": log,
    }
