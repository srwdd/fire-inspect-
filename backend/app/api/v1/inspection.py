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
import json
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from pydantic import BaseModel

from app.core.checklist_engine import checklist_engine
from app.api.v1.ws import ws_broadcast
from app.dependencies import verify_api_key, get_current_user

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
    list_owner_submissions, get_owner_submission,
    save_inspection, get_inspection, update_inspection_status, list_active_inspections,
    update_current_index, search_inspections as storage_search,
    save_finding, get_findings, init_db,
    save_rectifications, get_rectifications, update_rectification, get_pending_rectifications,
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
    assist_id: int = 0
    venue_addr: str = ""

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
def start_inspection(req: StartRequest, user: dict = Depends(get_current_user)):
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
        "org_id": req.org_id, "lead_id": req.lead_id, "assist_id": req.assist_id, "venue_addr": req.venue_addr,
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
    user: dict = Depends(get_current_user),
):
    states = storage_search(venue_name)
    results = []
    user_org = user.get("oid", 0)
    for state in states:
        if user_org and user_org != int(state.get("org_id") or 0): continue
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



# ── 进行中的检查（协办可加入） ──────────────────────

@router.get("/active")
def get_active_inspections(user: dict = Depends(get_current_user), include_completed: int = 1):
    """返回当前用户作为主办或协办的检查（进行中 + 最近完成的）"""
    from app.db.storage import list_recent_completed
    uid = user.get("uid", 0)
    oid = user.get("oid", 0)
    all_states = list_active_inspections(uid)
    results = []
    seen_ids = set()
    for state in all_states:
        seen_ids.add(state["inspection_id"])
        lead = state.get("lead_id", 0)
        assist = state.get("assist_id", 0)
        results.append({
            "inspection_id": state["inspection_id"],
            "venue_name": state.get("venue_name", ""),
            "venue_type": state.get("venue_type", ""),
            "date": state.get("started_at", "")[:10],
            "inspector": state.get("inspector", ""),
            "total_items": state.get("total_items", 0),
            "current_index": state.get("current_index", 0),
            "role": "lead" if uid == lead else "assist",
            "status": state.get("status", "in_progress"),
        })
    # 加上最近完成的检查
    if include_completed:
        completed = list_recent_completed(oid, limit=5)
        for insp in completed:
            if insp["inspection_id"] not in seen_ids:
                items = insp.get("items") or []
                fail_count = sum(1 for j in items if isinstance(j, dict) and j.get("result") == "fail")
                results.append({
                    "inspection_id": insp["inspection_id"],
                    "venue_name": insp.get("venue_name", ""),
                    "venue_type": insp.get("venue_type", ""),
                    "date": (insp.get("completed_at") or insp.get("started_at") or "")[:10],
                    "inspector": insp.get("inspector", ""),
                    "total_items": insp.get("total_items", 0),
                    "current_index": insp.get("current_index", 0),
                    "role": "lead",
                    "status": "completed",
                    "fail_count": fail_count,
                    "score": round((insp.get("total_items", 0) - fail_count) / max(insp.get("total_items", 1), 1) * 100),
                })
    results.sort(key=lambda x: x["date"], reverse=True)
    return {"code": 0, "data": results}



# ── 5. 整改跟踪 ──────────────────────────────────

class RectificationBatch(BaseModel):
    inspection_id: str
    items: list[dict]

@router.post("/{inspection_id}/rectifications")
def create_rectifications(inspection_id: str, items: list[dict]):
    """批量创建整改项"""
    save_rectifications(inspection_id, items)
    return {"code": 0, "msg": "整改项已保存", "data": {"count": len(items)}}

@router.get("/{inspection_id}/rectifications")
def list_rectifications(inspection_id: str):
    """获取检查的整改项列表"""
    items = get_rectifications(inspection_id)
    return {"code": 0, "data": items}

@router.put("/rectifications/{rect_id}")
def update_rect(rect_id: int, data: dict):
    """更新整改状态"""
    update_rectification(rect_id, **data)
    return {"code": 0, "msg": "已更新"}

@router.get("/pending-rectifications")
def list_pending_rectifications(user: dict = Depends(get_current_user)):
    """首页待整改提醒"""
    oid = user.get("oid", 0)
    tasks = get_pending_rectifications(oid)
    pending = [t for t in tasks if t["status"] == "pending"]
    rectified = [t for t in tasks if t["status"] == "rectified"]
    return {"code": 0, "data": {
        "total": len(tasks),
        "pending": len(pending),
        "pending_verify": len(rectified),
        "tasks": tasks
    }}


# ── 6. 历史对比 & 趋势 ──────────────────────────

@router.get("/venue-history")
def get_venue_history(venue_name: str = Query(""), venue_address: str = Query(""), user: dict = Depends(get_current_user)):
    """获取同一场所的历史检查记录"""
    from app.db.storage import search_inspections as search_ins
    oid = user.get("oid", 0)
    all_completed = search_ins("")
    # Filter by venue name
    records = []
    for insp in all_completed:
        vn = insp.get("venue_name", "")
        va = insp.get("venue_address", "") or insp.get("venue_addr", "")
        if venue_name and venue_name in vn:
            records.append(insp)
        elif venue_address and venue_address in va:
            records.append(insp)
    # Filter by org
    if oid:
        records = [r for r in records if int(r.get("org_id", 0) or 0) == oid]
    # Enrich with findings summary
    from app.db.storage import get_findings
    result = []
    for insp in records:
        findings = get_findings(insp["inspection_id"])
        fails = [f for f in findings if f.get("result") == "fail"]
        result.append({
            "inspection_id": insp["inspection_id"],
            "venue_name": insp.get("venue_name", ""),
            "date": (insp.get("completed_at") or insp.get("started_at", ""))[:10],
            "mode": insp.get("mode", "first"),
            "total": len(findings),
            "fail": len(fails),
            "mandatory_fail": sum(1 for f in fails if f.get("is_mandatory")),
            "important_fail": sum(1 for f in fails if f.get("severity") == "important"),
            "fails": [{"facility": f.get("facility",""), "note": f.get("note","")} for f in fails[:10]]
        })
    result.sort(key=lambda x: x["date"], reverse=True)
    return {"code": 0, "data": result}

@router.get("/trends")
def get_trends(user: dict = Depends(get_current_user)):
    """AI 隐患趋势分析"""
    from app.db.storage import search_inspections as search_ins, get_findings
    from datetime import datetime, timedelta
    from collections import Counter
    
    oid = user.get("oid", 0)
    all_completed = search_ins("")
    if oid:
        all_completed = [i for i in all_completed if int(i.get("org_id", 0) or 0) == oid]
    
    # Monthly stats
    monthly = {}
    fail_facilities = Counter()
    total_inspections = 0
    total_fails = 0
    total_items = 0
    
    for insp in all_completed:
        date_str = (insp.get("completed_at") or insp.get("started_at", ""))[:7]
        findings = get_findings(insp["inspection_id"])
        fails = [f for f in findings if f.get("result") == "fail"]
        
        month_key = date_str if date_str else "unknown"
        if month_key not in monthly:
            monthly[month_key] = {"total": 0, "fails": 0, "inspections": 0}
        monthly[month_key]["total"] += len(findings)
        monthly[month_key]["fails"] += len(fails)
        monthly[month_key]["inspections"] += 1
        
        for f in fails:
            fail_facilities[f.get("facility", "未知")] += 1
        total_inspections += 1
        total_fails += len(fails)
        total_items += len(findings)
    
    # Sort months
    sorted_months = sorted(monthly.keys())
    trend_data = [{"month": m, **monthly[m], "rate": round(monthly[m]["fails"]/max(monthly[m]["total"],1)*100, 1)} for m in sorted_months[-6:]]
    
    # Top fail facilities
    top_fails = [{"facility": k, "count": v} for k, v in fail_facilities.most_common(10)]
    
    # Trend direction
    recent_rates = [t["rate"] for t in trend_data[-3:]]
    trend = "上升" if len(recent_rates) >= 2 and recent_rates[-1] > recent_rates[0] else ("下降" if len(recent_rates) >= 2 and recent_rates[-1] < recent_rates[0] else "持平")
    
    return {"code": 0, "data": {
        "total_inspections": total_inspections,
        "total_fails": total_fails,
        "overall_rate": round(total_fails/max(total_items,1)*100, 1),
        "trend": trend,
        "monthly": trend_data,
        "top_fails": top_fails[:5],
        "latest_month": sorted_months[-1] if sorted_months else ""
    }}

# ── 数据看板统计 ──────────────────────────────────

@router.get("/stats")
def get_stats(user: dict = Depends(get_current_user)):
    """返回当前用户所在大队的检查统计数据"""
    uid = user.get("uid", 0)
    oid = user.get("oid", 0)

    all_states = list_active_inspections(0)  # 获取所有进行中的
    completed = storage_search("")  # 获取所有已完成的

    # 合并
    all_inspections = all_states + completed

    # 按大队过滤
    org_inspections = [s for s in all_inspections if int(s.get("org_id") or 0) == oid]

    total = len(org_inspections)
    in_progress = len([s for s in org_inspections if s.get("status") == "in_progress"])
    completed_count = total - in_progress

    # 汇总所有检查的 findings
    total_pass = 0
    total_fail = 0
    fail_by_facility = {}
    recent = []

    for insp in org_inspections:
        findings = get_findings(insp["inspection_id"])
        insp_pass = len([f for f in findings if f.get("result") == "pass"])
        insp_fail = len([f for f in findings if f.get("result") == "fail"])
        total_pass += insp_pass
        total_fail += insp_fail

        for f in findings:
            if f.get("result") == "fail":
                fac = f.get("facility", "未知")
                fail_by_facility[fac] = fail_by_facility.get(fac, 0) + 1

        # 最近5条
        if len(recent) < 5:
            recent.append({
                "inspection_id": insp["inspection_id"],
                "venue_name": insp.get("venue_name", ""),
                "date": insp.get("started_at", "")[:10],
                "status": insp.get("status", ""),
                "pass": insp_pass,
                "fail": insp_fail,
            })

    # 隐患排行 top 5
    hazard_ranking = sorted(fail_by_facility.items(), key=lambda x: x[1], reverse=True)[:5]
    hazard_ranking = [{"facility": k, "count": v} for k, v in hazard_ranking]

    total_judged = total_pass + total_fail
    pass_rate = round(total_pass / total_judged * 100, 1) if total_judged > 0 else 0

    return {"code": 0, "data": {
        "total": total,
        "in_progress": in_progress,
        "completed": completed_count,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "pass_rate": pass_rate,
        "hazard_ranking": hazard_ranking,
        "recent": recent,
    }}


# ── 3. 复查 — 开始 ──────────────────────────────────

@router.post("/recheck", response_model=RecheckResponse)
def start_recheck(req: RecheckRequest, user: dict = Depends(get_current_user)):
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
def get_pending_rechecks(user: dict = Depends(get_current_user)):
    """返回所有到期/即将到期的复查任务"""
    from app.services.reminder import get_pending_rechecks as fetch_pending
    tasks = fetch_pending()
    user_org = user.get("oid", 0)
    if user_org:
        tasks = [t for t in tasks if int(t.get("org_id", 0) or 0) == user_org]
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
def get_all_items(inspection_id: str, user: dict = Depends(get_current_user)):
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
def submit_judge(inspection_id: str, req: JudgeRequest, user: dict = Depends(get_current_user)):
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

    # WebSocket broadcast to assistant
    try:
        print(f"[WS-DEBUG] broadcasting to {inspection_id}: item={req.item_index} result={req.result}", flush=True)
        ws_broadcast(inspection_id, {
            "type": "judgment",
            "item_index": req.item_index,
            "result": req.result,
            "note": req.note,
            "from_role": user.get("role", ""),
            "from_uid": user.get("uid", 0),
            "judged_count": 0,
        })
    except Exception as ex:
        print(f"[WS-DEBUG] broadcast error: {ex}", flush=True)

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
    files: List[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
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

    images_bytes = [await f.read() for f in files]
    from app.core.photo_analyzer import analyze_photo
    result = await analyze_photo(
        images_bytes=images_bytes,
        item_context={"facility": item["facility"], "check_point": item["check_point"], "regulation": item.get("regulation", {})},
        api_key=api_key,
        base_url=_os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
        model=_os.environ.get("VISION_MODEL", "qwen-vl-max"),
    )

    # 自动填表建议
    print(f'[PHOTO-ANALYSIS] facility={item[chr(102)+chr(97)+chr(99)+chr(105)+chr(108)+chr(105)+chr(116)+chr(121)]} violation={result.get(chr(118)+chr(105)+chr(111)+chr(108)+chr(97)+chr(116)+chr(105)+chr(111)+chr(110))} confidence={result.get(chr(99)+chr(111)+chr(110)+chr(102)+chr(105)+chr(100)+chr(101)+chr(110)+chr(99)+chr(101),0)} reason={result.get(chr(114)+chr(101)+chr(97)+chr(115)+chr(111)+chr(110),chr(78)+chr(111)+chr(110)+chr(101))[:80]}', flush=True)
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
    files: List[UploadFile] = File(...),
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

    images_bytes = [await f.read() for f in files]
    from app.core.photo_analyzer import analyze_photo
    analysis = await analyze_photo(
        image_bytes=image_bytes,
        item_context={"facility": item["facility"], "check_point": item["check_point"], "regulation": item.get("regulation", {})},
        api_key=api_key,
        base_url=_os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
        model=_os.environ.get("VISION_MODEL", "qwen-vl-max"),
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
def generate_report(inspection_id: str, user: dict = Depends(get_current_user)):
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


# ── 业主自查管理 ──────────────────────────────────

@router.get("/owner-submissions")
def get_owner_submissions_api(org_id: int = 0):
    """消防员查看所有业主提交"""
    subs = list_owner_submissions(org_id)
    import json as _json
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
    } for s in subs]}


@router.delete("/{inspection_id}")
def delete_inspection(inspection_id: str, user: dict = Depends(get_current_user)):
    """删除进行中的检查"""
    from app.db.storage import _connect
    state=_require_state(inspection_id)
    if state.get("status")!="in_progress":
        raise HTTPException(400,"只能删除进行中的检查")
    with _connect() as conn:
        conn.execute("DELETE FROM inspections WHERE id=?",(inspection_id,))
        conn.execute("DELETE FROM findings WHERE inspection_id=?",(inspection_id,))
        conn.commit()
    return {"code":0,"msg":"已删除"}

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
def export_report(inspection_id: str, format: str = Query("html", pattern="^(html|excel)$")):
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
def review_inspection(inspection_id: str, action: str = Query(..., pattern="^(approve|reject)$"), req: WorkflowRequest = WorkflowRequest()):
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



