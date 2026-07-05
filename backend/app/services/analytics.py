"""监督员驾驶舱 — 数据统计分析服务 Phase 4.1"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.db.storage import search_inspections, get_findings


def get_dashboard_stats(inspector: str = "") -> Dict[str, Any]:
    """构建驾驶舱全量统计数据"""
    all_inspections = search_inspections()
    if inspector:
        all_inspections = [
            i for i in all_inspections
            if i.get("inspector", "") == inspector
        ]

    now = datetime.now()
    this_month = now.strftime("%Y-%m")
    last_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    monthly_insp = [i for i in all_inspections if i.get("started_at", "")[:7] == this_month]
    last_month_insp = [i for i in all_inspections if i.get("started_at", "")[:7] == last_month]

    # 汇总各检查的发现
    all_findings = []
    for insp in all_inspections:
        findings = get_findings(insp["inspection_id"])
        for f in findings:
            f["_insp_date"] = insp.get("started_at", "")[:10]
            f["_venue_name"] = insp.get("venue_name", insp.get("venue_type", ""))
            f["_venue_type"] = insp.get("venue_type", "")
            f["_inspector"] = insp.get("inspector", "")
        all_findings.extend(findings)

    monthly_findings = [f for f in all_findings if f.get("_insp_date", "")[:7] == this_month]
    fails = [f for f in all_findings if f.get("result") == "fail"]
    monthly_fails = [f for f in monthly_findings if f.get("result") == "fail"]

    # 风险分布
    color_counts = _count_colors(all_inspections)

    # 高频隐患
    top_hazards = _top_hazards(fails)

    # 场所类型分布
    venue_type_stats = Counter(i.get("venue_type", "未知") for i in all_inspections)

    # 个人效率
    inspector_efficiency = _inspector_stats(all_inspections, now)

    # 整改率
    rectification_rate = _rectification_rate(all_findings)

    return {
        "overview": {
            "total_inspections": len(all_inspections),
            "this_month": len(monthly_insp),
            "last_month": len(last_month_insp),
            "trend": "up" if len(monthly_insp) >= len(last_month_insp) else "down",
            "total_findings": len(all_findings),
            "total_fails": len(fails),
            "fail_rate": round(len(fails) / len(all_findings), 3) if all_findings else 0,
            "rectification_rate": rectification_rate,
        },
        "risk_distribution": {
            "red": color_counts.get("red", 0),
            "orange": color_counts.get("orange", 0),
            "yellow": color_counts.get("yellow", 0),
            "green": color_counts.get("green", 0),
        },
        "monthly": {
            "this_month": {
                "inspections": len(monthly_insp),
                "findings": len(monthly_findings),
                "fails": len(monthly_fails),
                "fail_rate": round(len(monthly_fails) / len(monthly_findings), 3) if monthly_findings else 0,
            },
        },
        "top_hazards": top_hazards[:10],
        "venue_types": [
            {"type": k, "count": v}
            for k, v in venue_type_stats.most_common(10)
        ],
        "inspector_efficiency": inspector_efficiency,
    }


def _count_colors(inspections: List[Dict]) -> Dict[str, int]:
    """统计红橙黄绿分布"""
    colors = Counter()
    for insp in inspections:
        findings = get_findings(insp["inspection_id"])
        fails_list = [f for f in findings if f.get("result") == "fail"]
        if not fails_list:
            colors["green"] += 1
            continue
        mandatory = sum(1 for f in fails_list if f.get("is_mandatory"))
        important = sum(1 for f in fails_list if f.get("severity") == "important" and not f.get("is_mandatory"))
        score = max(0, 100 - mandatory * 30 - important * 15 - (len(fails_list) - mandatory - important) * 5)
        if score <= 40:
            colors["red"] += 1
        elif score <= 60:
            colors["orange"] += 1
        elif score <= 80:
            colors["yellow"] += 1
        else:
            colors["green"] += 1
    return dict(colors)


def _top_hazards(fails: List[Dict]) -> List[Dict]:
    """高频隐患 Top10"""
    facility_counter = Counter(f.get("facility", "") for f in fails)
    return [
        {"facility": fac, "count": cnt, "pct": round(cnt / len(fails) * 100, 1) if fails else 0}
        for fac, cnt in facility_counter.most_common(10)
    ]


def _inspector_stats(inspections: List[Dict], now: datetime) -> List[Dict]:
    """个人效率统计"""
    by_inspector: Dict[str, List] = {}
    for insp in inspections:
        name = insp.get("inspector", "未知")
        if name not in by_inspector:
            by_inspector[name] = []
        by_inspector[name].append(insp)

    this_month = now.strftime("%Y-%m")
    stats = []
    for name, insp_list in by_inspector.items():
        monthly = [i for i in insp_list if i.get("started_at", "")[:7] == this_month]
        total_fails = 0
        for insp in monthly:
            findings = get_findings(insp["inspection_id"])
            total_fails += sum(1 for f in findings if f.get("result") == "fail")
        stats.append({
            "inspector": name,
            "total_inspections": len(insp_list),
            "this_month": len(monthly),
            "avg_items_per_inspection": round(
                sum(i.get("total_items", 0) for i in insp_list) / len(insp_list), 1
            ) if insp_list else 0,
            "monthly_fails": total_fails,
        })
    stats.sort(key=lambda x: x["this_month"], reverse=True)
    return stats


def _rectification_rate(all_findings: List[Dict]) -> float:
    """整改率: 有整改状态的fail中, 已闭环的比例"""
    fail_with_status = [f for f in all_findings
                        if f.get("result") == "fail" and f.get("rectification_status")]
    if not fail_with_status:
        return 0.0
    closed = [f for f in fail_with_status if "已整改" in f.get("rectification_status", "")
              or "closed" in f.get("rectification_status", "").lower()]
    return round(len(closed) / len(fail_with_status), 3) if fail_with_status else 0.0
