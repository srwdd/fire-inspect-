"""AI 增强服务 — 语音填表 / 报告摘要 / 法规问答"""
import json, os, logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
BASE_URL = os.environ.get("SILICONFLOW_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
TEXT_MODEL = os.environ.get("SILICONFLOW_TEXT_MODEL", "Qwen/Qwen3.6-35B-A3B")

async def _call_llm(messages: list, temperature: float = 0.3) -> str:
    """调用文本 LLM"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            BASE_URL + "/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": TEXT_MODEL, "messages": messages, "temperature": temperature, "max_tokens": 1024}
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def ai_judge_from_voice(voice_text: str, item_context: dict) -> dict:
    """从语音描述中提取结构化判定"""
    prompt = f"""你是一名消防监督检查专家。根据消防员的语音描述，输出JSON格式的判定结果。

检查项: {item_context.get('facility', '')} - {item_context.get('check_point', '')}
法规依据: {item_context.get('regulation', item_context.get('source', ''))}
消防员口述: "{voice_text}"

请输出JSON（不要其他文字）:
{{"result": "pass|fail|na", "note": "问题描述（25字以内）", "suggested_fix": "整改建议（30字以内）", "confidence": 0.0-1.0}}

判定规则:
- pass: 消防员说"没问题""合格""正常""符合要求"等
- fail: 消防员说"不合格""有问题""损坏""缺失""不符合"等
- na: 消防员说"不涉及""不适用""没有"等
- note 要精炼，提取消防员描述的核心问题
- confidence 表示判定可信度"""

    try:
        content = await _call_llm([{"role": "user", "content": prompt}])
        # Extract JSON from response
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
    except Exception as e:
        logger.warning(f"AI judge failed: {e}")
    return {"result": "fail", "note": voice_text[:50], "suggested_fix": "请现场核实后制定整改方案", "confidence": 0.3}


async def ai_generate_summary(inspection_data: dict) -> str:
    """AI 生成检查报告摘要"""
    findings = inspection_data.get("findings", [])
    fails = [f for f in findings if f.get("result") == "fail"]
    passes = [f for f in findings if f.get("result") == "pass"]
    mandatory_fails = [f for f in fails if f.get("is_mandatory")]

    fail_summary = "\n".join([f"- {f.get('facility','')}: {f.get('note','不合格')}" for f in fails[:10]])

    prompt = f"""你是消防救援大队的检查报告撰写助手。请根据以下检查数据，撰写一段150字以内的检查报告摘要。

场所: {inspection_data.get('venue_name', '')}
检查日期: {inspection_data.get('date', '')}
检查人: {inspection_data.get('inspector', '')}
总计: {len(findings)}项 | 合格: {len(passes)} | 不合格: {len(fails)}
强制性条文违犯: {len(mandatory_fails)}项

不合格项:
{fail_summary}

要求:
- 开头一句话概括检查结果
- 点出最严重的2-3个问题
- 结尾给出整改期限建议
- 语言正式、简洁，符合消防文书风格
- 直接输出摘要文字，不要加"摘要："前缀"""

    try:
        return await _call_llm([{"role": "user", "content": prompt}], temperature=0.5)
    except Exception as e:
        logger.warning(f"AI summary failed: {e}")
        return f"本次检查共{len(findings)}项，合格{len(passes)}项，不合格{len(fails)}项，其中强制性条文违犯{len(mandatory_fails)}项。建议限期整改。"


async def ai_regulation_qa(question: str, context_rules: list = None) -> dict:
    """AI 法规智能问答"""
    context = ""
    if context_rules:
        context = "\n\n相关法规条文:\n" + "\n".join([
            f"- [{r.get('source','')}] {r.get('title','')}: {r.get('check_point','')[:200]}"
            for r in context_rules[:5]
        ])

    prompt = f"""你是中国消防法规专家。请根据消防法规知识回答以下问题。

问题: {question}
{context}

要求:
- 引用具体法规条文（如 GB 50016-2014 第X条）
- 给出具体数值或标准（如果有）
- 回答简洁明了，200字以内
- 如果问题超出消防法规范围，回答"该问题不在消防法规范围内" """

    try:
        content = await _call_llm([{"role": "user", "content": prompt}], temperature=0.3)
        return {"answer": content, "source": "AI + 法规库"}
    except Exception as e:
        return {"answer": f"法规查询失败: {e}", "source": "error"}
