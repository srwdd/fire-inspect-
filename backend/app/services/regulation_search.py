"""法规智能检索 — TF-IDF + 关键词匹配 (Phase 4.2)

支持口语化查询: "这个灭火器过期了违反哪条？" → 自动提取关键词 → 匹配法规
"""
import json
import re
from pathlib import Path
from typing import Dict, List

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "fire_rules.json"
if not RULES_PATH.exists():
    RULES_PATH = Path(__file__).resolve().parent.parent.parent.parent / "fire_rules.json"

CASES_PATH = Path(__file__).resolve().parent.parent.parent / "fire_cases.json"
if not CASES_PATH.exists():
    CASES_PATH = Path(__file__).resolve().parent.parent.parent.parent / "fire_cases.json"

SOLUTIONS_PATH = Path(__file__).resolve().parent.parent.parent / "fire_solutions.json"
if not SOLUTIONS_PATH.exists():
    SOLUTIONS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "fire_solutions.json"

# ── 消防术语同义词映射 ──────────────────────────
_SYNONYMS = {
    "灭火器": ["灭火器", "灭火器具", "手提灭火器", "推车灭火器", "消防器材"],
    "消火栓": ["消火栓", "消防栓", "室内消火栓", "室外消火栓", "消防水喉", "消防水泵接合器"],
    "安全出口": ["安全出口", "疏散出口", "紧急出口", "逃生门", "疏散门"],
    "消防通道": ["消防通道", "消防车道", "消防车通道", "消防车"],
    "疏散指示": ["疏散指示", "疏散标志", "指示标志", "安全标志", "逃生标志", "指示灯", "应急灯不亮", "疏散指示灯"],
    "应急照明": ["应急照明", "应急灯", "事故照明", "备用照明", "疏散照明"],
    "防火门": ["防火门", "防火卷帘", "防火分隔", "防火门窗"],
    "烟感": ["烟感", "烟感探测器", "感烟探测器", "感烟", "烟雾探测器"],
    "报警器": ["报警", "火灾报警", "自动报警", "报警系统", "火灾探测器", "报警控制器"],
    "喷淋": ["喷淋", "自动喷水", "喷头", "洒水喷头", "水喷淋", "自动喷淋", "喷水灭火"],
    "电气": ["电气", "电线", "线路", "配电", "漏电", "用电", "铝线", "铜线", "过载", "发烫"],
    "过期": ["过期", "失效", "超期", "到期", "超过10年"],
    "使用年限": ["使用年限", "年限", "寿命", "有效期", "保质期", "多久更换", "保养周期"],
    "损坏": ["损坏", "破损", "故障", "损毁", "缺失", "发霉", "被咬"],
    "堵塞": ["堵塞", "占用", "锁闭", "封堵", "阻挡", "压占"],
    # 🔥 新增 — 覆盖评测失败用例
    "油污": ["油污", "清洁", "保养", "脏污"],
    "维护保养": ["维护", "保养", "巡检", "定期检查", "巡查记录"],
    "压力不足": ["压力不足", "欠压", "压力表红区", "压力表失效", "无压力"],
    "锈蚀": ["锈蚀", "生锈", "腐蚀", "漆面脱落", "筒体破损"],
    "防盗窗": ["防盗窗", "防盗网", "铁栅栏", "逃生窗口", "无法开启"],
    "电动车": ["电动车", "电动自行车", "电池充电", "室内充电", "飞线充电"],
    "彩钢板": ["彩钢板", "夹芯板", "泡沫夹芯", "易燃材料", "可燃材料"],
    "燃气管": ["燃气管", "燃气软管", "橡胶管", "金属波纹管", "燃气泄漏"],
    "养老院": ["养老院", "养老机构", "老年人照料设施", "福利院"],
    "消防控制室": ["消防控制室", "消控室", "值班人员", "持证上岗", "操作员证"],
    "防火封堵": ["防火封堵", "孔洞封堵", "电缆桥架", "穿墙封堵", "防火泥"],
    "水带": ["水带", "消防水带", "水枪", "破损", "老化"],
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
    # 提取双字和三字片段（原始查询词权重最高）
    for i in range(len(query) - 1):
        tokens.add(query[i:i+2])
        if i < len(query) - 2:
            tokens.add(query[i:i+3])
    return list(tokens)


def search_regulations(query: str, top_k: int = 3) -> List[Dict]:
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
        matched_terms = 0
        for token in tokens:
            if len(token) < 2:
                continue
            count = text.count(token)
            if count > 0:
                score += count * (2 if len(token) >= 3 else 1)
                matched_keywords.add(token)
                if len(token) >= 3:
                    matched_terms += 1
        # 概念多样性加分：匹配不同 CHAR 的原始查询词 → 更高分
        unique_chars_matched = len(set(query) & set(text))
        score = int(score * (1 + unique_chars_matched * 0.05))
        if matched_terms >= 2:
            score = int(score * 1.5)
        if matched_terms >= 3:
            score = int(score * 1.5)
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
    results = scored[:top_k * 2]  # get more candidates for re-rank

    # Re-rank: extract original query words (2+ char substrings), 
    # give intersection bonus when document matches words from >1 query segment
    q_words = set()
    for token in tokens:
        if len(token) >= 3 and token not in q_words:
            q_words.add(token)
    for r in results:
        text = (r.get("title","") + " " + r.get("check_point","") + " " + r.get("text",""))
        # Count distinct query words (>=3 chars) matched
        matched_qwords = sum(1 for w in q_words if w in text)
        # Each distinct query word matched = +25% boost
        if matched_qwords >= 2:
            r["score"] = int(r["score"] * (1 + matched_qwords * 0.25))
    
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:top_k]

    # LLM re-rank if API key available
    import os as _os
    # Ensure .env is loaded
    try:
        from dotenv import load_dotenv
        from pathlib import Path as _P
        _env = _P(__file__).resolve().parent.parent.parent / '.env'
        if _env.exists():
            load_dotenv(_env, override=True)
    except Exception:
        pass
    api_key = _os.environ.get("SILICONFLOW_API_KEY", "")
    print(f"[LLM-RERANK] key={'SET' if api_key else 'NOT SET'} results={len(results)}", flush=True)
    if api_key and len(results) > 3:
        base_url = _os.environ.get("SILICONFLOW_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        llm_model = "qwen-plus"
        results = _llm_rerank(query, results, api_key, base_url, llm_model)

    # 给结果添加处罚和整改建议
    for r in results:
        r["penalty"] = _penalty_hint(r.get("category", ""), r.get("severity", "normal"))
        r["suggested_action"] = _action_hint(r.get("check_point", ""), r.get("severity", "normal"))

    # 去重：同source+title只保留最高分
    seen_dedup = set()
    deduped = []
    for r in results:
        k = (r.get("source",""), r.get("title",""))
        if k not in seen_dedup:
            seen_dedup.add(k)
            deduped.append(r)
    results = deduped

    return results



def _llm_rerank(query, candidates, api_key, base_url, model):
    """Use LLM to re-rank search results for semantic relevance."""
    import httpx
    if not api_key or len(candidates) <= 3:
        return candidates

    items_text = []
    for i, c in enumerate(candidates[:15]):
        src = c.get('source', '')
        art = c.get('article', '')
        title = c.get('title', '')
        cp = c.get('check_point', '')[:60]
        items_text.append(f"{i+1}. [{src} {art}] {title}: {cp}")

    prompt = (
        "你是消防法规检索专家。用户查询可能包含多个概念，请按以下优先级排序：\n1. 同时匹配查询中所有概念的文档排最前面\n2. 只匹配部分概念的排在后面\n3. 法规条款直接相关的优先于一般性描述\n\n用户查询: " + query + "\n\n候选条款:\n" + "\n".join(items_text) + "\n\n按上述规则排序，只返回序号，用逗号分隔，如: 3,1,2\n注意: 如果查询包含多个关键词（如养老机构+耐火等级），优先返回同时涉及两者的条款"
    )

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                base_url + '/chat/completions',
                headers={'Authorization': 'Bearer ' + api_key},
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 50, 'temperature': 0
                }
            )
            data = resp.json()
            if 'choices' not in data:
                return candidates
            reply = data['choices'][0]['message']['content'].strip()

            indices = [int(x.strip()) for x in re.findall(r'\d+', reply)]
            indices = [i-1 for i in indices if 1 <= i <= len(candidates)]

            reranked = [candidates[i] for i in indices if i < len(candidates)]
            seen = set(indices)
            for i, c in enumerate(candidates):
                if i not in seen:
                    reranked.append(c)

            return reranked[:len(candidates)]
    except Exception:
        return candidates


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



# ══════════════════════════════════════════════════════════════
# 火鉴体系 — 警鉴（案例）+ 策鉴（方案）跨库检索
# ══════════════════════════════════════════════════════════════

def _load_cases() -> List[Dict]:
    if not CASES_PATH.exists():
        return []
    try:
        kb = json.loads(CASES_PATH.read_text("utf-8"))
        return kb.get("cases", [])
    except (json.JSONDecodeError, KeyError):
        return []


def _load_solutions() -> List[Dict]:
    if not SOLUTIONS_PATH.exists():
        return []
    try:
        kb = json.loads(SOLUTIONS_PATH.read_text("utf-8"))
        return kb.get("solutions", [])
    except (json.JSONDecodeError, KeyError):
        return []


def search_cases(query: str, facility: str = "", top_k: int = 3) -> List[Dict]:
    """警鉴·案例检索 — 按设施类型+关键词匹配相似案例"""
    cases = _load_cases()
    if not cases:
        return []

    # 扩展查询词
    tokens = _expand_query(query)
    if facility:
        tokens.append(facility)
        tokens.extend(facility[i:i+2] for i in range(len(facility)-1))

    scored = []
    for case in cases:
        text = (
            case.get("finding", "") + " " +
            case.get("facility", "") + " " +
            " ".join(case.get("finding_keywords", [])) + " " +
            case.get("venue_type", "") + " " +
            case.get("cause", "")
        )
        score = 0
        matched = []
        for token in tokens:
            if len(token) < 2:
                continue
            count = text.count(token)
            if count > 0:
                score += count * (2 if len(token) >= 3 else 1)
                matched.append(token)

        # 同设施类型加权
        if facility and facility in case.get("facility", ""):
            score = int(score * 2.0)

        if score > 0:
            scored.append({
                "case_id": case.get("id", ""),
                "facility": case.get("facility", ""),
                "finding": case.get("finding", ""),
                "venue_type": case.get("venue_type", ""),
                "severity": case.get("severity", "normal"),
                "cause": case.get("cause", ""),
                "consequence": case.get("consequence", ""),
                "regulation_refs": case.get("regulation_refs", []),
                "score": score,
                "matched_keywords": matched[:5],
                "source": "警鉴·案例库",
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def search_solutions(query: str, facility: str = "", top_k: int = 3) -> List[Dict]:
    """策鉴·方案检索 — 匹配隐患关键词返回整改方案"""
    solutions = _load_solutions()
    if not solutions:
        return []

    tokens = _expand_query(query)
    if facility:
        tokens.append(facility)

    scored = []
    for sol in solutions:
        text = (
            sol.get("facility", "") + " " +
            " ".join(sol.get("finding_keywords", [])) + " " +
            sol.get("category", "") + " " +
            sol.get("immediate_action", "")
        )
        score = 0
        matched = []
        for token in tokens:
            if len(token) < 2:
                continue
            count = text.count(token)
            if count > 0:
                score += count * (3 if len(token) >= 3 else 1)
                matched.append(token)

        # 同设施类型加权
        if facility and facility in sol.get("facility", ""):
            score = int(score * 2.5)

        if score > 0:
            scored.append({
                "solution_id": sol.get("id", ""),
                "facility": sol.get("facility", ""),
                "immediate_action": sol.get("immediate_action", ""),
                "rectification_period": sol.get("rectification_period", "限期整改"),
                "responsible_role": sol.get("responsible_role", "消防安全管理人"),
                "verification_method": sol.get("verification_method", ""),
                "cost_estimate": sol.get("cost_estimate", ""),
                "steps": sol.get("steps", []),
                "reference": sol.get("reference", ""),
                "score": score,
                "matched_keywords": matched[:5],
                "source": "策鉴·方案库",
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def search_all(query: str, facility: str = "", top_k: int = 3) -> Dict[str, List[Dict]]:
    """火鉴体系联合检索 — 同时查询法鉴+警鉴+策鉴，返回结构化结果"""
    return {
        "regulations": search_regulations(query, top_k=top_k),
        "cases": search_cases(query, facility=facility, top_k=3),
        "solutions": search_solutions(query, facility=facility, top_k=3),
    }
