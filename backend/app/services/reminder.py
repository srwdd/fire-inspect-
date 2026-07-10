"""复查到期提醒服务 — Phase 2.3"""
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.db.storage import search_inspections, get_findings


def get_pending_rechecks() -> List[Dict[str, Any]]:
    """返回所有需要复查的任务（红/橙档 + 已过复查期限或即将到期）"""
    completed = search_inspections()
    pending = []

    for insp in completed:
        findings = get_findings(insp["inspection_id"])
        if not findings:
            continue

        # 从 findings 中重建评估结果
        fail_items = [f for f in findings if f.get("result") == "fail"]
        if not fail_items:
            continue

        # 快速计算风险等级
        mandatory_fails = sum(1 for f in fail_items if f.get("is_mandatory"))
        important_fails = sum(1 for f in fail_items if f.get("severity") == "important" and not f.get("is_mandatory"))
        score = max(0, 100 - mandatory_fails * 30 - important_fails * 15 - (len(fail_items) - mandatory_fails - important_fails) * 5)

        # 确定复查期限
        if score <= 40:
            color, days = "red", 15
        elif score <= 60:
            color, days = "orange", 30
        elif score <= 80:
            color, days = "yellow", 60
        else:
            color, days = "green", 180

        if color == "green":
            continue  # 绿档不需要强制复查

        # 计算复查期限
        started = insp.get("started_at", "")
        insp_date = datetime.fromisoformat(started) if started else datetime.now()
        deadline = insp_date + timedelta(days=days)
        now = datetime.now()
        overdue_days = (now - deadline).days

        # 只返回已到期或7天内到期的
        if overdue_days < -7:
            continue

        pending.append({
            "inspection_id": insp["inspection_id"],
            "venue_name": insp.get("venue_name", insp.get("venue_type", "")),
            "venue_type": insp.get("venue_type", ""),
            "location": insp.get("location", ""),
            "inspector": insp.get("inspector", ""),
            "org_id": insp.get("org_id"),
            "inspection_date": started[:10] if started else "",
            "score": score,
            "color": color,
            "fail_count": len(fail_items),
            "mandatory_fail": mandatory_fails,
            "important_fail": important_fails,
            "recheck_deadline": deadline.strftime("%Y-%m-%d"),
            "overdue_days": max(0, overdue_days),
            "urgency": "urgent" if overdue_days >= 0 else "upcoming",
        })

    # 排序：逾期优先 → 评分低优先
    pending.sort(key=lambda x: (-x["overdue_days"], x["score"]))
    return pending
