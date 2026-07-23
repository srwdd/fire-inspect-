
"""火鉴·警鉴 — 自动案例沉淀
每次检查提交 fail 判定时，自动将新发现存入案例库
"""
import json, os
from datetime import datetime
from pathlib import Path

CASES_PATH = Path(__file__).resolve().parent.parent.parent / "fire_cases.json"
if not CASES_PATH.exists():
    CASES_PATH = Path(__file__).resolve().parent.parent.parent.parent / "fire_cases.json"

def _load_cases():
    if not CASES_PATH.exists():
        return []
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        kb = json.load(f)
    return kb.get("cases", [])

def _save_cases(cases):
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        kb = json.load(f)
    kb["cases"] = cases
    kb["knowledge_base"]["built_at"] = datetime.now().strftime("%Y-%m-%d")
    with open(CASES_PATH, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)

def precipitate_finding(finding: dict):
    """将 fail 判定沉淀为案例。自动去重：同设施+同关键词72h内不重复存入"""
    if finding.get("result") != "fail":
        return  # 只沉淀不合格项

    facility = finding.get("facility", "")
    note = finding.get("note", "").strip()
    check_point = finding.get("check_point", "")

    if not note or len(note) < 3:
        return  # 没有实质性描述，跳过

    # 检查去重：72h内同设施+同check_point不重复
    cases = _load_cases()
    now = datetime.now()
    for c in cases:
        created = c.get("created", "")
        if c.get("facility") == facility and c.get("finding", "").find(note[:20]) >= 0:
            try:
                age = (now - datetime.strptime(created, "%Y-%m-%d")).days
                if age < 3:
                    return  # 3天内重复，跳过
            except:
                pass

    # 构建案例条目
    new_case = {
        "id": f"CAUTO{len(cases)+1:04d}",
        "facility": facility,
        "category": finding.get("category", ""),
        "finding": f"{check_point}: {note}"[:120],
        "finding_keywords": [w for w in (note + check_point).replace("，", ",").replace("、", ",").split(",") if len(w.strip()) >= 2][:5],
        "venue_type": finding.get("scene", ""),
        "severity": finding.get("severity", "normal"),
        "regulation_refs": [finding.get("rule_id", "")] if finding.get("rule_id") else [],
        "cause": note[:60],
        "consequence": "",
        "photo_features": "",
        "typical_scene": finding.get("scene", ""),
        "created": now.strftime("%Y-%m-%d"),
        "source": "自动沉淀·实地检查",
    }

    cases.append(new_case)
    _save_cases(cases)
    print(f"[警鉴] 自动沉淀案例: {new_case['id']} {facility} — {new_case['finding'][:60]}")
    return new_case["id"]
