"""法规智能检索 — TF-IDF + 关键词匹配 (Phase 4.2)

支持口语化查询: "这个灭火器过期了违反哪条？" → 自动提取关键词 → 匹配法规
"""
import json
from pathlib import Path
from typing import Dict, List

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "fire_rules.json"
if not RULES_PATH.exists():
    RULES_PATH = Path(__file__).resolve().parent.parent.parent.parent / "fire_rules.json"

# ── 消防术语同义词映射 ──────────────────────────
_SYNONYMS = {
    "灭火器": ["灭火器", "灭火器具", "手提灭火器", "推车灭火器", "消防器材"],
    "消火栓": ["消火栓", "消防栓", "室内消火栓", "室外消火栓", "消防水喉"],
    "安全出口": ["安全出口", "疏散出口", "紧急出口", "逃生门", "疏散门"],
    "消防通道": ["消防通道", "消防车道", "消防车通道", "消防车"],
    "疏散指示": ["疏散指示", "疏散标志", "指示标志", "安全标志", "逃生标志"],
    "应急照明": ["应急照明", "应急灯", "事故照明", "备用照明", "疏散照明"],
    "防火门": ["防火门", "防火卷帘", "防火分隔", "防火门窗"],
    "烟感": ["烟感", "烟感探测器", "感烟探测器", "感烟", "烟雾探测器"],
    "报警器": ["报警", "火灾报警", "自动报警", "报警系统", "火灾探测器"],
    "喷淋": ["喷淋", "自动喷水", "喷头", "洒水喷头", "水喷淋"],
    "电气": ["电气", "电线", "线路", "配电", "漏电", "用电"],
    "过期": ["过期", "失效", "超期", "到期"],
    "损坏": ["损坏", "破损", "故障", "损毁", "缺失"],
    "堵塞": ["堵塞", "占用", "锁闭", "封堵", "阻挡"],
}


def _load_rules() -> List[Dict]:
    if not RULES_PATH.exists():
        return []
    try:
        kb = json.loads(RULES_PATH.read_text("utf-8"))
        return kb.get("rules", [])
    except (json.JSONDecodeError, KeyError):
        return []


def _expand_query(query: str) -> List[str]:
    """扩展查询词: 同义词扩展 + 分词"""
    tokens = set()
    # 按同义词扩展
    for keyword, synonyms in _SYNONYMS.items():
        if any(s in query for s in synonyms):
            tokens.update(synonyms)
    # 也保留原始查询词
    tokens.add(query)
    # 提取双字和三字片段
    for i in range(len(query) - 1):
        tokens.add(query[i:i+2])
        if i < len(query) - 2:
            tokens.add(query[i:i+3])
    return list(tokens)


def search_regulations(query: str, top_k: int = 5) -> List[Dict]:
    """智能检索法规: 口语查询 → 匹配的法规条款"""
    rules = _load_rules()
    if not rules:
        return []

    tokens = _expand_query(query)

    # 对每条规则计算匹配分
    scored = []
    for rule in rules:
        text = (
            rule.get("title", "") + " " +
            rule.get("facility", "") + " " +
            rule.get("check_point", "") + " " +
            rule.get("source", "") + " " +
            rule.get("text", "")
        )
        score = 0
        matched_keywords = set()
        for token in tokens:
            if len(token) < 2:
                continue
            count = text.count(token)
            if count > 0:
                score += count * (2 if len(token) >= 3 else 1)
                matched_keywords.add(token)
        if score > 0:
            scored.append({
                "rule_id": rule.get("id", ""),
                "title": rule.get("title", ""),
                "facility": rule.get("facility", rule.get("title", "")),
                "check_point": rule.get("check_point", ""),
                "category": rule.get("category", ""),
                "severity": rule.get("severity", "normal"),
                "source": rule.get("source", ""),
                "article": rule.get("article", ""),
                "text": (rule.get("text") or "")[:200],
                "source_type": rule.get("source_type", ""),
                "score": round(score, 1),
                "matched_keywords": list(matched_keywords)[:5],
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    results = scored[:top_k]

    # 给结果添加处罚和整改建议
    for r in results:
        r["penalty"] = _penalty_hint(r.get("category", ""), r.get("severity", "normal"))
        r["suggested_action"] = _action_hint(r.get("check_point", ""), r.get("severity", "normal"))

    return results


def _penalty_hint(category: str, severity: str) -> str:
    if severity == "important":
        return "依据《消防法》第60条，可处5000元-5万元罚款"
    if category == "消防管理":
        return "依据《消防法》第67条，责令限期改正"
    return "依据相关法规条款处理"


def _action_hint(check_point: str, severity: str) -> str:
    if "立即" in check_point or severity == "important":
        return "建议立即整改"
    return "建议限期整改"
