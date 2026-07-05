"""多跳推理证据链 — 对标 FireAgent evidence-tree RAG

4层推理结构:
  事实层(Facts) → 规则层(Rules) → 推理层(Reasoning) → 处置层(Action)

输入: photo_analyzer 返回的 analysis dict
输出: 完整 evidence_chain JSON
"""
import json
from pathlib import Path
from typing import Any, Dict, List


def build_evidence_chain(analysis: Dict, item_context: Dict) -> Dict[str, Any]:
    """基于照片分析结果构建完整证据链"""
    facility = item_context.get("facility", "")
    check_point = item_context.get("check_point", "")

    # ── 第1层: 事实层 ──
    facts = _build_facts(analysis, facility)

    # ── 第2层: 规则层 ──
    rules = _build_rules(analysis, item_context)

    # ── 第3层: 推理层 ──
    reasoning = _build_reasoning(facts, rules, analysis)

    # ── 第4层: 处置层 ──
    action = _build_action(analysis, facts)

    return {
        "evidence_id": f"EV-{_ts()}",
        "facility": facility,
        "check_point": check_point,
        "conclusion": {
            "violation": analysis.get("violation"),
            "confidence": analysis.get("confidence", 0),
            "summary": _summarize(analysis),
        },
        "chain": {
            "facts": facts,
            "rules": rules,
            "reasoning": reasoning,
            "action": action,
        },
    }


def _build_facts(analysis: Dict, facility: str) -> Dict:
    """事实层: 从分析结果提取客观视觉事实"""
    visual_facts = []
    detail = analysis.get("detail", {})
    reason = analysis.get("reason", "")

    # 提取设备类型
    device = detail.get("设备类型", facility)
    if device:
        visual_facts.append(f"识别到设备: {device}")

    # 提取隐患描述中的事实
    desc = detail.get("隐患描述", reason)
    if desc:
        visual_facts.append(f"观察结果: {desc}")

    # 提取危害等级
    level = detail.get("隐患等级", "无")
    if level != "无" and level:
        visual_facts.append(f"危害等级: {level}")

    return {
        "observations": visual_facts,
        "device_type": device,
        "hazard_detected": analysis.get("violation") is True,
        "raw_detail": desc,
    }


def _build_rules(analysis: Dict, item_context: Dict) -> Dict:
    """规则层: 匹配适用的法规条款"""
    regulation = item_context.get("regulation", {})
    matched = list(analysis.get("regulation") or [])

    # 如果分析结果没有匹配到法规，使用预设的
    if not matched:
        src = regulation.get("source", "")
        txt = regulation.get("text", "")[:200]
        if src:
            matched.append(f"{src}: {txt}")

    # 从法规库中补充相关条款
    related = _find_related_regulations(analysis, item_context)

    return {
        "primary": matched,
        "related": related,
        "compliance_status": "违规" if analysis.get("violation") else ("合规" if analysis.get("violation") is False else "待确认"),
    }


def _find_related_regulations(analysis: Dict, item_context: Dict) -> List[str]:
    """从 fire_rules.json 查找相关法规补充条款"""
    rules_path = Path(__file__).resolve().parent.parent.parent / "fire_rules.json"
    if not rules_path.exists():
        rules_path = Path(__file__).resolve().parent.parent.parent.parent / "fire_rules.json"
    if not rules_path.exists():
        return []

    try:
        kb = json.loads(rules_path.read_text("utf-8"))
        all_rules = kb.get("rules", [])
    except (json.JSONDecodeError, KeyError):
        return []

    facility = item_context.get("facility", "")
    analysis.get("hazard_code")

    related = []
    for rule in all_rules:
        rule_title = rule.get("title", "") + rule.get("facility", "")
        # 按设施类型和隐患编码匹配
        if facility and facility in rule_title:
            src = rule.get("source", "")
            art = rule.get("article", "")
            ref = f"{src} 第{art}条" if art else src
            if ref and ref not in related and ref not in "\n".join(analysis.get("regulation") or []):
                related.append(ref)
        if len(related) >= 3:
            break

    return related[:3]


def _build_reasoning(facts: Dict, rules: Dict, analysis: Dict) -> Dict:
    """推理层: 从事实到结论的逻辑推导"""
    steps = []
    violation = analysis.get("violation")

    # 步骤1: 观察到的事实
    observations = facts.get("observations", [])
    if observations:
        steps.append({
            "step": 1,
            "type": "observation",
            "content": "；".join(observations),
        })

    # 步骤2: 适用的法规
    primary_rules = rules.get("primary", [])
    if primary_rules:
        steps.append({
            "step": 2,
            "type": "regulation_match",
            "content": f"适用法规: {'; '.join(primary_rules)}",
        })

    # 步骤3: 逻辑推理
    if violation is True:
        reasoning_text = "观察到的现象不符合上述法规要求，存在消防安全隐患"
        if analysis.get("hazard_code"):
            reasoning_text += f"（隐患类型: {analysis.get('hazard_category', '')}/{analysis.get('hazard_name', '')}）"
        steps.append({"step": 3, "type": "deduction", "content": reasoning_text})
    elif violation is False:
        steps.append({"step": 3, "type": "deduction", "content": "观察到的现象符合上述法规要求，未发现消防安全隐患"})
    else:
        steps.append({"step": 3, "type": "deduction", "content": "证据不足，无法做出明确判定，建议人工复核"})

    # 步骤4: 置信度评估
    confidence = analysis.get("confidence", 0)
    if confidence >= 0.9:
        conf_note = "证据充分，结论可信度高"
    elif confidence >= 0.6:
        conf_note = "证据较充分，结论可信度中等"
    else:
        conf_note = "证据不足，建议结合现场其他检查项综合判断"

    steps.append({"step": 4, "type": "confidence", "content": f"置信度 {confidence:.0%} — {conf_note}"})

    return {"steps": steps, "logic_path": "deductive"}


def _build_action(analysis: Dict, facts: Dict) -> Dict:
    """处置层: 具体的整改和执法建议"""
    rectification = analysis.get("rectification", "")
    deadline = analysis.get("deadline", "")
    violation = analysis.get("violation")

    measures = []

    # 整改措施
    if violation and rectification:
        measures.append({"type": "rectification", "content": rectification, "deadline": deadline})
        if deadline and "立即" in deadline:
            measures.append({"type": "urgency", "content": "此项需立即整改，整改完成前应采取临时安全措施"})

    # 处罚建议
    if violation:
        if analysis.get("hazard_code") and any(c in (analysis.get("hazard_code") or "") for c in ["EXIT", "FIRE_LANE", "HYDR"]):
            measures.append({"type": "penalty_warning", "content": "依据《消防法》第60条，可对单位处5000元以上5万元以下罚款"})

    # 复查建议
    if violation:
        measures.append({"type": "recheck", "content": f"建议复查期限: {deadline or '3天'}"})

    if not violation and violation is not None:
        measures.append({"type": "compliance", "content": "该项检查合格，纳入常规管理"})

    if violation is None:
        measures.append({"type": "manual_review", "content": "AI无法判断，请人工确认后决定处置措施"})

    return {"measures": measures}


def _summarize(analysis: Dict) -> str:
    violation = analysis.get("violation")
    if violation is True:
        return f"不合格 — {analysis.get('hazard_name') or analysis.get('hazard_category', '消防隐患')}"
    if violation is False:
        return "合格 — 符合消防法规要求"
    return "待确认 — AI无法判断，需人工复核"


def _ts() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d%H%M%S")
