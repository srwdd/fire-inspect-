"""
检查流程 API v2 — SQLite 持久化 + Vision LLM 照片分析
合并自: 本地 inspection_api.py (SQLite) + 服务器 inspection.py (计算器/业主告知书)
"""
from __future__ import annotations

import os as _os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from pydantic import BaseModel

from app.core.checklist_engine import checklist_engine
from app.dependencies import verify_api_key

# ── 加载 .env 文件 ────────────────────────────────────
_ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _val = _line.split("=", 1)
            _key, _val = _key.strip(), _val.strip().strip('"').strip("'")
            if _key not in _os.environ:
                _os.environ[_key] = _val

router = APIRouter(prefix="", tags=["检查流程"], dependencies=[Depends(verify_api_key)])

# ── SQLite 持久化存储 ───────────────────────────────
from app.db.storage import (
    save_inspection, get_inspection, update_inspection_status,
    update_current_index, search_inspections as storage_search,
    save_finding, get_findings, init_db,
)
init_db()


# ── Pydantic models ──────────────────────────────────

class StartRequest(BaseModel):
    venue_type: str
    inspection_type: str = "preopen"
    location: str = ""
    inspector: str = ""
    staff_count: int = 0
    floor_count: int = 0
    area_sqm: int = 0
    building_count: int = 1
    sub_type: str = ""
    org_id: int = 0
    lead_id: int = 0
    venue_addr: str = "

class RecheckRequest(BaseModel):
    previous_inspection_id: str
    inspector: str = ""

class JudgeRequest(BaseModel):
    item_index: int
    result: Literal["pass", "fail"]
    note: str = ""
    judge_source: str = "manual"
    rectification_status: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None


# ── Response models ─────────────────────────────────

class StartData(BaseModel):
    inspection_id: str
    venue_name: str = ""
    total_items: int = 0
    mandatory_count: int = 0
    sample_count: int = 0
    staff_sample: Optional[dict] = None
    floor_sample: Optional[dict] = None

class StartResponse(BaseModel):
    code: int = 0
    data: StartData

class RecheckData(BaseModel):
    inspection_id: str
    mode: str = "recheck"
    previous_date: str = ""
    total_items: int = 0
    previously_failed: int = 0
    previously_important_fail: int = 0

class RecheckResponse(BaseModel):
    code: int = 0
    data: RecheckData

class JudgeData(BaseModel):
    recorded: bool = True
    next_item_available: bool = True

class JudgeResponse(BaseModel):
    code: int = 0
    data: JudgeData

# ── Helper ──────────────────────────────────────────

def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 距离计算（米）"""
    r = 6371000
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))

def _require_state(inspection_id: str) -> Dict[str, Any]:
    state = get_inspection(inspection_id)
    if not state:
        raise HTTPException(status_code=404, detail="检查记录不存在")
    return state


# ── 1. 首次检查 — 开始 ──────────────────────────────

@router.post("/start", response_model=StartResponse)
def start_inspection(req: StartRequest):
    PREOPEN_VENUES = {"hotel", "mall", "entertainment", "restaurant"}
    if req.inspection_type == "preopen" and req.venue_type not in PREOPEN_VENUES:
        raise HTTPException(400, detail="该场所不属于公众聚集场所，不适用开业前检查，请选择日常检查")

    insp_id = f"INSP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    scene_info = checklist_engine.get_scene_info(req.venue_type)
    items = checklist_engine.get_check_items(req.venue_type, req.inspection_type)

    staff_sample = checklist_engine.calc_staff_sample(req.staff_count) if req.staff_count > 0 else None
    floor_sample = checklist_engine.calc_floor_sample(req.floor_count) if req.floor_count > 0 else None
    mandatory_count = sum(1 for i in items if i["is_mandatory"])

    state = {
        "inspection_id": insp_id, "mode": "first",
        "venue_type": req.venue_type, "venue_name": scene_info.get("name", req.venue_type),
        "location": req.location, "inspector": req.inspector,
        "staff_count": req.staff_count, "floor_count": req.floor_count, "area_sqm": req.area_sqm,
        "staff_sample": staff_sample, "floor_sample": floor_sample,
        "org_id": req.org_id, "lead_id": req.lead_id, "venue_addr": req.venue_addr,
        "total_items": len(items), "mandatory_count": mandatory_count,
        "sample_count": len(items) - mandatory_count,
        "current_index": 0, "items": items,
        "started_at": datetime.now().isoformat(), "status": "in_progress",
        "previous_inspection_id": None, "previous_fail_ids": [],
    }
    save_inspection(state)

    return {"code": 0, "data": {
        "inspection_id": insp_id, "venue_name": state["venue_name"],
        "total_items": state["total_items"], "mandatory_count": mandatory_count,
        "sample_count": state["sample_count"], "staff_sample": staff_sample,
        "floor_sample": floor_sample,
    }}


# ── 2. 搜索历史 ─────────────────────────────────────

@router.get("/search")
def search_inspections(
    venue_name: str = Query(""),
    date_from: str = Query(""),
):
    states = storage_search(venue_name)
    results = []
    for state in states:
        findings = get_findings(state["inspection_id"])
        fail_items = [f for f in findings if f.get("result") == "fail"]
        important_fails = [f for f in fail_items if f.get("severity") == "important"]
        results.append({
            "inspection_id": state["inspection_id"],
            "venue_name": state.get("venue_name", ""),
            "venue_type": state.get("venue_type", ""),
            "location": state.get("location", ""),
            "inspector": state.get("inspector", ""),
            "date": state.get("started_at", "")[:10],
            "total_items": state.get("total_items", 0),
            "fail_count": len(fail_items),
            "important_fail_count": len(important_fails),
            "findings_summary": [
                {"facility": f.get("facility", ""), "result": f.get("result", ""),
                 "severity": f.get("severity", ""),
                 "detail": f.get("note", f.get("check_point", ""))}
                for f in fail_items[:10]
            ],
        })
    results.sort(key=lambda x: x["date"], reverse=True)
    return {"code": 0, "data": results}


# ── 3. 复查 — 开始 ──────────────────────────────────

@router.post("/recheck", response_model=RecheckResponse)
def start_recheck(req: RecheckRequest):
    prev_state = _require_state(req.previous_inspection_id)
    prev_findings = get_findings(req.previous_inspection_id)
    prev_fail_ids = [f["rule_id"] for f in prev_findings if f.get("result") == "fail"]

    insp_id = f"RECHECK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    items = checklist_engine.sort_items_for_recheck(prev_state.get("items", []), prev_fail_ids)

    state = {
        **{k: v for k, v in prev_state.items() if k not in ("items", "inspection_id", "started_at", "status", "current_index")},
        "inspection_id": insp_id, "mode": "recheck",
        "inspector": req.inspector or prev_state.get("inspector", ""),
        "total_items": len(items), "current_index": 0, "items": items,
        "started_at": datetime.now().isoformat(), "status": "in_progress",
        "previous_inspection_id": req.previous_inspection_id,
        "previous_fail_ids": prev_fail_ids,
        "previous_date": prev_state.get("started_at", "")[:10],
    }
    save_inspection(state)

    return {"code": 0, "data": {
        "inspection_id": insp_id, "mode": "recheck",
        "previous_date": state["previous_date"],
        "total_items": state["total_items"],
        "previously_failed": len(prev_fail_ids),
        "previously_important_fail": len([f for f in prev_findings
            if f.get("result") == "fail" and f.get("severity") == "important"]),
    }}


# ── 4. 复查到期提醒 ─────────────────────────────────

@router.get("/pending-rechecks")
def get_pending_rechecks():
    """返回所有到期/即将到期的复查任务"""
    from app.services.reminder import get_pending_rechecks as fetch_pending
    tasks = fetch_pending()
    urgent = [t for t in tasks if t["urgency"] == "urgent"]
    upcoming = [t for t in tasks if t["urgency"] == "upcoming"]
    return {"code": 0, "data": {
        "total": len(tasks),
        "urgent": len(urgent),
        "upcoming": len(upcoming),
        "tasks": tasks,
    }}


# ── 4a. 获取指定检查项 ──────────────────────────────

@router.get("/{inspection_id}/item/{item_index}")
def get_item(inspection_id: str, item_index: int):
    state = _require_state(inspection_id)
    items = state["items"]
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=400, detail="检查项索引超出范围")

    item = items[item_index]
    findings = get_findings(inspection_id)
    prev_judgment = None
    for f in findings:
        if f.get("item_index") == item_index:
            prev_judgment = {"result": f.get("result"), "note": f.get("note", "")}
            break

    response_item = {
        "item_index": item_index, "total_items": len(items),
        "preopen_section": item.get("preopen_section", 0),
        "preopen_sub": item.get("preopen_sub", 0),
        "preopen_order": item.get("preopen_order", 0),
        "step": item.get("step", 5),
        "facility": item["facility"], "check_point": item["check_point"],
        "check_method": item.get("check_method", ""),
        "category": item.get("category", "技术条件"),
        "severity": item.get("severity", "normal"),
        "is_mandatory": item.get("is_mandatory", False),
        "is_recheck_item": item.get("is_recheck_item", False),
        "regulation": item.get("regulation", {}),
        "province_regulations": item.get("province_regulations", []),
        "previous_judgment": prev_judgment,
    }

    if state["mode"] == "recheck" and item.get("is_recheck_item"):
        prev_id = state.get("previous_inspection_id", "")
        prev_findings = get_findings(prev_id) if prev_id else []
        prev = next((f for f in prev_findings if f.get("rule_id") == item["rule_id"]), None)
        if prev:
            response_item["previous_result"] = {
                "date": state.get("previous_date", ""),
                "result": prev.get("result", ""),
                "detail": prev.get("note", ""),
                "photos": prev.get("photos", []),
            }

    return {"code": 0, "data": response_item}


# ── 4b. 获取下一检查项 ──────────────────────────────

@router.get("/{inspection_id}/items")
def get_all_items(inspection_id: str):
    """获取检查单全部项目 — 供前端快速跳转预加载"""
    state = _require_state(inspection_id)
    items = state.get("items", [])
    for i, item in enumerate(items):
        item["item_index"] = i
    return {"code": 0, "data": items}


@router.get("/{inspection_id}/next")
def get_next_item(inspection_id: str):
    state = _require_state(inspection_id)
    if state["status"] != "in_progress":
        return {"code": 0, "data": None, "message": "检查已完成"}

    idx = state["current_index"]
    items = state["items"]

    if idx >= len(items):
        update_inspection_status(inspection_id, "completed")
        return {"code": 0, "data": None, "message": "所有检查项已完成", "is_complete": True}

    item = items[idx]
    response_item = {
        "item_index": idx, "total_items": len(items),
        "facility": item["facility"], "check_point": item["check_point"],
        "check_method": item.get("check_method", ""),
        "category": item.get("category", "技术条件"),
        "severity": item.get("severity", "normal"),
        "is_mandatory": item.get("is_mandatory", False),
        "is_recheck_item": item.get("is_recheck_item", False),
        "regulation": item.get("regulation", {}),
        "province_regulations": item.get("province_regulations", []),
    }

    if state["mode"] == "recheck" and item.get("is_recheck_item"):
        prev_id = state.get("previous_inspection_id", "")
        prev_findings = get_findings(prev_id) if prev_id else []
        prev = next((f for f in prev_findings if f.get("rule_id") == item["rule_id"]), None)
        if prev:
            response_item["previous_result"] = {
                "date": state.get("previous_date", ""),
                "result": prev.get("result", ""),
                "detail": prev.get("note", ""),
                "photos": prev.get("photos", []),
            }

    return {"code": 0, "data": response_item, "is_complete": False}


# ── 5. 提交判断 ─────────────────────────────────────

@router.post("/{inspection_id}/judge", response_model=JudgeResponse)
def submit_judge(inspection_id: str, req: JudgeRequest):
    state = _require_state(inspection_id)
    items = state["items"]
    if req.item_index >= len(items):
        raise HTTPException(status_code=400, detail="检查项索引超出范围")

    item = items[req.item_index]
    finding = {
        "item_index": req.item_index, "rule_id": item["rule_id"],
        "facility": item["facility"], "check_point": item["check_point"],
        "category": item.get("category", ""), "severity": item.get("severity", "normal"),
        "is_mandatory": item.get("is_mandatory", False),
        "result": req.result, "note": req.note,
        "judge_source": req.judge_source,
        "rectification_status": req.rectification_status,
        "judged_at": datetime.now().isoformat(), "photos": [],
        "gps": {"lat": req.lat, "lng": req.lng} if req.lat is not None else None,
    }
    save_finding(inspection_id, finding)
    update_current_index(inspection_id, req.item_index + 1)

    # GPS防作假: 检查与之前判定的位置偏差
    gps_warning = None
    if req.lat is not None:
        prev_findings = get_findings(inspection_id)
        for pf in prev_findings:
            pg = pf.get("gps") or {}
            if pg.get("lat") is not None:
                dist = _haversine(req.lat, req.lng, pg["lat"], pg["lng"])
                if dist > 500:  # 500米偏差告警
                    gps_warning = f"GPS偏差{int(dist)}m，请确认巡检位置"

    return {"code": 0, "data": {
        "recorded": True,
        "next_item_available": req.item_index + 1 < len(items),
        "gps_warning": gps_warning,
    }}


# ── 5b. AI判定反馈闭环 ─────────────────────────────

class PhotoFeedbackRequest(BaseModel):
    item_index: int
    ai_violation: Optional[bool] = None
    ai_confidence: float = 0.0
    ai_hazard_code: Optional[str] = None
    inspector_result: Literal["pass", "fail"]
    inspector_note: str = ""


@router.get("/ai-accuracy-stats")
def get_ai_accuracy():
    from app.services.feedback import get_accuracy_stats
    return {"code": 0, "data": get_accuracy_stats()}


# ── 6. 拍照辅助判断 (Vision LLM) ────────────────────

@router.post("/{inspection_id}/photo")
async def photo_analyze(
    inspection_id: str,
    item_index: int = Form(...),
    file: UploadFile = File(...),
):
    state = _require_state(inspection_id)
    items = state["items"]
    if item_index >= len(items):
        raise HTTPException(status_code=400, detail="检查项索引超出范围")

    item = items[item_index]
    api_key = _os.environ.get("SILICONFLOW_API_KEY", "")
    if not api_key or api_key == "sk-your-key-here":
        return {"code": 0, "data": {
            "item": {"facility": item["facility"], "check_point": item["check_point"], "regulation": item.get("regulation", {})},
            "analysis": {"violation": None, "reason": "请在 .env 中设置 SILICONFLOW_API_KEY 后启用AI图片分析", "confidence": 0, "visual_facts": [], "suggested_result": ""},
            "message": "AI图片分析功能待API Key配置后启用",
        }}

    image_bytes = await file.read()
    from app.core.photo_analyzer import analyze_photo
    result = await analyze_photo(
        image_bytes=image_bytes,
        item_context={"facility": item["facility"], "check_point": item["check_point"], "regulation": item.get("regulation", {})},
        api_key=api_key,
        base_url=_os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
        model=_os.environ.get("VISION_MODEL", "deepseek-chat"),
    )

    # 自动填表建议
    auto_result = "fail" if result.get("violation") else ("pass" if result.get("violation") is False else "")
    regulation_text = "; ".join(result.get("regulation") or [])
    auto_note = (
        f"[AI分析] {result.get('reason', '')}\n"
        f"隐患分类: {result.get('hazard_name') or result.get('hazard_category', '未分类')}\n"
        f"法规依据: {regulation_text}\n"
        f"整改建议: {result.get('rectification', '请人工判断')}"
    ) if result.get("violation") else result.get("reason", "")

    return {"code": 0, "data": {
        "item": {
            "facility": item["facility"],
            "check_point": item["check_point"],
            "regulation": item.get("regulation", {}),
        },
        "analysis": {
            "violation": result.get("violation"),
            "hazard_code": result.get("hazard_code"),
            "hazard_category": result.get("hazard_category"),
            "hazard_name": result.get("hazard_name"),
            "reason": result.get("reason", ""),
            "confidence": result.get("confidence", 0),
            "regulation": result.get("regulation") or [],
            "rectification": result.get("rectification", ""),
            "deadline": result.get("deadline", ""),
            # 自动填表字段
            "suggested_result": auto_result,
            "suggested_note": auto_note,
            "suggested_rectification_status": result.get("deadline", ""),
        },
        "message": "AI分析完成" if result.get("violation") is not None else "AI无法判断，请人工确认",
    }}


# ── 6a. 证据链推理 ────────────────────────────────

@router.post("/{inspection_id}/photo/evidence")
async def photo_evidence(
    inspection_id: str,
    item_index: int = Form(...),
    file: UploadFile = File(...),
):
    """拍照 → 4层证据链推理 (对标FireAgent)"""
    state = _require_state(inspection_id)
    items = state["items"]
    if item_index >= len(items):
        raise HTTPException(status_code=400, detail="检查项索引超出范围")

    item = items[item_index]
    api_key = _os.environ.get("SILICONFLOW_API_KEY", "")
    if not api_key or api_key == "sk-your-key-here":
        return {"code": 0, "data": {"error": "API Key 未配置"}}

    image_bytes = await file.read()
    from app.core.photo_analyzer import analyze_photo
    analysis = await analyze_photo(
        image_bytes=image_bytes,
        item_context={"facility": item["facility"], "check_point": item["check_point"], "regulation": item.get("regulation", {})},
        api_key=api_key,
        base_url=_os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
        model=_os.environ.get("VISION_MODEL", "deepseek-chat"),
    )
    from app.services.evidence_chain import build_evidence_chain
    chain = build_evidence_chain(analysis, {
        "facility": item["facility"], "check_point": item["check_point"],
        "regulation": item.get("regulation", {}),
    })
    return {"code": 0, "data": chain}


@router.post("/{inspection_id}/photo/feedback")
def submit_photo_feedback(inspection_id: str, req: PhotoFeedbackRequest):
    """监督员纠正AI判定 → 写入反馈闭环"""
    state = _require_state(inspection_id)
    items = state["items"]
    facility = items[req.item_index]["facility"] if req.item_index < len(items) else ""
    from app.services.feedback import record_feedback
    result = record_feedback(
        inspection_id=inspection_id, item_index=req.item_index, facility=facility,
        ai_violation=req.ai_violation, ai_confidence=req.ai_confidence,
        ai_hazard_code=req.ai_hazard_code,
        inspector_result=req.inspector_result, inspector_note=req.inspector_note,
    )
    return {"code": 0, "data": result}


# ── 7a. 路线导航 ───────────────────────────────────

@router.get("/{inspection_id}/route")
def get_route(inspection_id: str):
    """返回按物理位置排序的检查路线（最短路径）"""
    state = _require_state(inspection_id)
    items = state.get("items", [])
    findings = get_findings(inspection_id)
    judged_idx = {f["item_index"] for f in findings}

    # 将未判定的项按 section_order 或 preopen_order 排序（模拟物理位置）
    remaining = [
        {"item_index": i, "facility": it.get("facility", ""), "check_point": it.get("check_point", "")[:40],
         "section_order": it.get("section_order") or it.get("preopen_order") or 9999,
         "step": it.get("step", 5), "step_name": it.get("step_name", "")}
        for i, it in enumerate(items) if i not in judged_idx
    ]
    remaining.sort(key=lambda x: (x["section_order"], x["item_index"]))

    # 当前未判定的第一个就是"下一个要去的位置"
    current = None
    if remaining:
        c = remaining[0]
        current = {
            "item_index": c["item_index"],
            "facility": c["facility"],
            "check_point": c["check_point"],
            "navigation_hint": _nav_hint(c),
        }

    return {"code": 0, "data": {
        "total_items": len(items),
        "judged": len(judged_idx),
        "remaining": len(remaining),
        "next_stop": current,
        "route_summary": [
            {"step": i + 1, "item_index": r["item_index"], "facility": r["facility"],
             "hint": _nav_hint(r)} for i, r in enumerate(remaining[:10])
        ],
    }}


def _nav_hint(item: dict) -> str:
    """根据检查项特征生成导航提示"""
    item.get("step_name", "")
    facility = item.get("facility", "")
    step = item.get("step", 0)
    hints = {
        1: "入口处核查许可证照",
        2: "前往消防管理办公室",
        3: "检查建筑外围消防车道和防火间距",
        4: "沿疏散走道检查安全出口和疏散指示",
        5: "前往消防控制室",
        6: "检查消火栓和自动喷水系统",
        7: "检查灭火器、防火门、防排烟",
        8: "检查厨房燃气、电气线路",
    }
    hint = hints.get(step, "继续巡检")
    if facility:
        hint = f"{hint} → {facility}"
    return hint


# ── 7. 生成报告 ─────────────────────────────────────

@router.get("/{inspection_id}/report")
def generate_report(inspection_id: str):
    state = _require_state(inspection_id)
    findings = get_findings(inspection_id)
    fail_items = [f for f in findings if f.get("result") == "fail"]
    pass_items = [f for f in findings if f.get("result") == "pass"]

    assessment = checklist_engine.calculate_assessment(findings)
    mandatory_fails = [f for f in fail_items if f.get("is_mandatory")]
    important_fails = [f for f in fail_items if f.get("severity") == "important" and not f.get("is_mandatory")]
    normal_fails = [f for f in fail_items if f.get("severity") == "normal"]

    return {"code": 0, "data": {
        "inspection_id": inspection_id, "mode": state.get("mode", "first"),
        "venue_name": state.get("venue_name", ""), "venue_type": state.get("venue_type", ""),
        "location": state.get("location", ""), "inspector": state.get("inspector", ""),
        "date": state.get("started_at", "")[:10],
        "previous_date": state.get("previous_date", ""),
        "summary": {
            "total": len(findings), "checked": len(findings),
            "pass": len(pass_items), "fail": len(fail_items),
            "mandatory_fail": len(mandatory_fails),
            "important_fail": len(important_fails),
            "normal_fail": len(normal_fails),
        },
        "assessment": assessment,
        "findings_by_severity": {
            "mandatory": mandatory_fails, "important": important_fails, "normal": normal_fails,
        },
        "all_findings": findings,
    }}


# ── 8. 整改告知单 ───────────────────────────────────

@router.get("/{inspection_id}/rectification-notice")
def rectification_notice(inspection_id: str):
    state = _require_state(inspection_id)
    findings = get_findings(inspection_id)
    fail_items = [f for f in findings if f.get("result") == "fail"]

    mandatory_violations, important_hazards, normal_hazards = [], [], []
    rank = 0
    for f in fail_items:
        rank += 1
        entry = {
            "rank": rank, "facility": f.get("facility", ""),
            "check_point": f.get("check_point", ""), "detail": f.get("note", ""),
            "is_mandatory": f.get("is_mandatory", False), "severity": f.get("severity", "normal"),
        }
        if f.get("is_mandatory"): mandatory_violations.append(entry)
        elif f.get("severity") == "important": important_hazards.append(entry)
        else: normal_hazards.append(entry)

    return {"code": 0, "data": {
        "venue_name": state.get("venue_name", ""),
        "location": state.get("location", ""),
        "inspection_date": state.get("started_at", "")[:10],
        "inspector": state.get("inspector", ""),
        "total_hazards": len(fail_items),
        "mandatory_violations": mandatory_violations,
        "important_hazards": important_hazards,
        "normal_hazards": normal_hazards,
    }}


# ── 9. 四色评估 ─────────────────────────────────────

@router.get("/{inspection_id}/assessment")
def get_assessment(inspection_id: str):
    state = _require_state(inspection_id)
    findings = get_findings(inspection_id)
    assessment = checklist_engine.calculate_assessment(findings)
    next_date = (datetime.now() + timedelta(days=assessment["next_recheck_days"])).strftime("%Y-%m-%d")

    return {"code": 0, "data": {
        **assessment,
        "venue_name": state.get("venue_name", ""),
        "inspection_date": state.get("started_at", "")[:10],
        "next_recheck_deadline": next_date,
        "suggestions": _generate_suggestions(assessment),
    }}


def _generate_suggestions(assessment: Dict) -> List[str]:
    suggestions = []
    color = assessment.get("color", "green")
    days = assessment.get("next_recheck_days", 90)
    radar = assessment.get("radar", {})
    suggestions.append(f"{days}日内安排复查")
    weak_areas = [k for k, v in radar.items() if v < 50]
    if weak_areas:
        suggestions.append(f"重点复查: {'、'.join(weak_areas)}类问题")
    if color in ("red", "orange"):
        suggestions.append("建议约谈消防安全管理人")
    if color == "red":
        suggestions.append("建议通报属地政府")
        suggestions.append("符合条件的可采取临时查封措施")
    return suggestions


# ── 10. 计算工具 ────────────────────────────────────

@router.post("/calc/{calc_type}")
def calculate(calc_type: str, params: dict):
    from app.core.calculator import calc_fire_zone, calc_water_tank, calc_extinguisher, calc_evacuation
    try:
        if calc_type == "fire_zone":
            r = calc_fire_zone(area=float(params.get("area",0)), floors=int(params.get("floors",1)),
                has_sprinkler=params.get("sprinkler",True), is_highrise=params.get("highrise",False))
        elif calc_type == "water_tank":
            r = calc_water_tank(area=float(params.get("area",0)), floors=int(params.get("floors",1)),
                venue_type=params.get("venue","hotel"), has_sprinkler=params.get("sprinkler",True),
                is_highrise=params.get("highrise",False))
        elif calc_type == "evacuation":
            r = calc_evacuation(people_count=int(params.get("people",0)), floor_num=int(params.get("floor",1)),
                is_highrise=params.get("highrise",False))
        elif calc_type == "extinguisher":
            r = calc_extinguisher(area=float(params.get("area",0)), hazard_level=params.get("level","中危险级"))
        else:
            return {"code":1,"msg":f"不支持: {calc_type}"}
        return {"code":0,"data":r}
    except Exception as e:
        return {"code":1,"msg":f"计算失败: {e}"}


# ── 11. 业主告知书 ──────────────────────────────────

@router.get("/{inspection_id}/owner-report")
def get_owner_report(inspection_id: str):
    findings = get_findings(inspection_id)
    inspection = get_inspection(inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="检查记录不存在")
    fails = [f for f in findings if f.get("result") == "fail"]
    assessment = checklist_engine.calculate_assessment([
        {"rule_id":f.get("rule_id",""),"result":f.get("result","pass"),"severity":f.get("severity","normal"),
         "is_mandatory":f.get("is_mandatory",False),"category":f.get("category","技术条件"),
         "facility":f.get("facility",""),"note":f.get("note",f.get("check_point",""))} for f in findings
    ])
    urgent, deadline, suggest = [], [], []
    for f in fails:
        item = {"facility":f.get("facility",""),"check_point":f.get("check_point",""),
                "note":f.get("note",""),"source":f.get("source","")}
        if f.get("is_mandatory") or f.get("severity")=="important": urgent.append(item)
        elif f.get("severity")=="normal": deadline.append(item)
        else: suggest.append(item)
    return {"code":0,"data":{
        "venue_name": inspection.get("location","") or inspection.get("venue_type",""),
        "date": inspection.get("date",""),"inspector": inspection.get("inspector",""),
        "score": assessment["score"],"color": assessment["color"],"color_label": assessment["color_label"],
        "total_fails": len(fails),"urgent_fixes": urgent,"deadline_fixes": deadline,"suggestions": suggest,
        "supervision_measures": assessment["supervision_measures"],"next_recheck_days": assessment["next_recheck_days"]}}


# ── 12a. 法规智能检索 ──────────────────────────────

@router.get("/regulation-search")
def smart_regulation_search(
    query: str = Query(..., description="口语化查询，如'灭火器过期违反哪条'"),
    top_k: int = Query(5, ge=1, le=20),
):
    """TF-IDF 智能法规检索 — 支持口语化查询"""
    from app.services.regulation_search import search_regulations
    results = search_regulations(query, top_k)
    return {"code": 0, "data": {
        "query": query,
        "total": len(results),
        "results": results,
    }}


# ── 12b. 扫码查设备历史 ────────────────────────────

@router.get("/facility-history")
def facility_history(facility: str = Query(...), venue_type: str = Query("")):
    """扫码获取设备历史——返回该设备类型在所有检查中的最近结果"""
    all_inspections = list(storage_search(""))
    history = []
    seen_locations = set()
    for insp in all_inspections[:30]:
        if not isinstance(insp, dict):
            continue
        insp_id = insp.get("inspection_id", insp.get("id", ""))
        if not insp_id:
            continue
        findings = get_findings(insp_id)
        for f in findings:
            if facility in f.get("facility", ""):
                key = insp.get("location", insp.get("venue_name", ""))
                if key in seen_locations:
                    continue
                seen_locations.add(key)
                history.append({
                    "inspection_id": insp["inspection_id"],
                    "venue": key,
                    "date": insp.get("started_at", "")[:10],
                    "facility": f.get("facility", ""),
                    "check_point": f.get("check_point", ""),
                    "result": f.get("result", ""),
                    "note": f.get("note", "")[:100],
                    "photos": (f.get("photos") or [])[:3],
                })
        if len(history) >= 10:
            break

    fail_count = sum(1 for h in history if h["result"] == "fail")
    return {"code": 0, "data": {
        "facility": facility,
        "total_records": len(history),
        "fail_count": fail_count,
        "history": history,
        "summary": f"该设备近期检查{len(history)}次，不合格{fail_count}次" if history else "该设备暂无检查记录",
    }}


# ── 12a. 报告导出 ──────────────────────────────────

@router.get("/{inspection_id}/report/export")
def export_report(inspection_id: str, format: str = Query("html", regex="^(html|excel)$")):
    """导出检查报告: ?format=html (可打印PDF) 或 ?format=excel"""
    from fastapi.responses import Response, HTMLResponse
    from app.services.report_export import generate_html_report, generate_excel_data

    if format == "excel":
        data = generate_excel_data(inspection_id)
        return Response(
            content=data,
            media_type="application/vnd.ms-excel",
            headers={"Content-Disposition": f"attachment; filename=inspection_{inspection_id}.csv"},
        )
    else:
        html = generate_html_report(inspection_id)
        return HTMLResponse(content=html)


# ── 11b. 审批工作流 ─────────────────────────────────

class WorkflowRequest(BaseModel):
    reviewer: str = ""
    comment: str = ""


@router.post("/{inspection_id}/submit")
def submit_for_review(inspection_id: str, req: WorkflowRequest = WorkflowRequest()):
    """监督员提交检查报告→队长审核"""
    from app.services.workflow import transition
    r = transition(inspection_id, "submitted", req.reviewer, req.comment)
    if not r["ok"]:
        raise HTTPException(400, r["error"])
    return {"code": 0, "data": r}


@router.post("/{inspection_id}/review")
def review_inspection(inspection_id: str, action: str = Query(..., regex="^(approve|reject)$"), req: WorkflowRequest = WorkflowRequest()):
    """队长审核: ?action=approve→已审核 / ?action=reject→驳回"""
    from app.services.workflow import transition
    new_status = "reviewed" if action == "approve" else "rejected"
    r = transition(inspection_id, new_status, req.reviewer, req.comment)
    if not r["ok"]:
        raise HTTPException(400, r["error"])
    return {"code": 0, "data": r}


@router.post("/{inspection_id}/approve")
def approve_inspection(inspection_id: str, req: WorkflowRequest = WorkflowRequest()):
    """大队批准→最终归档"""
    from app.services.workflow import transition
    r = transition(inspection_id, "approved", req.reviewer, req.comment)
    if not r["ok"]:
        raise HTTPException(400, r["error"])
    return {"code": 0, "data": r}


# ── 12. 驾驶舱统计 ─────────────────────────────────

@router.get("/dashboard-stats")
def get_dashboard(inspector: str = Query("")):
    """监督员驾驶舱全量统计数据"""
    from app.services.analytics import get_dashboard_stats
    return {"code": 0, "data": get_dashboard_stats(inspector)}



