"""AI判定反馈闭环 — 对标海南模式"采集→标注→迭代"闭环

监督员纠正AI判定 → 累计纠正样本 → 自动调整 prompt 示例
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

FEEDBACK_FILE = Path(__file__).resolve().parent.parent.parent / "ai_feedback.json"


def _load() -> List[Dict]:
    if not FEEDBACK_FILE.exists():
        return []
    try:
        return json.loads(FEEDBACK_FILE.read_text("utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save(records: List[Dict]) -> None:
    FEEDBACK_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), "utf-8")


def record_feedback(
    inspection_id: str,
    item_index: int,
    facility: str,
    ai_violation: bool | None,
    ai_confidence: float,
    ai_hazard_code: str | None,
    inspector_result: str,
    inspector_note: str,
) -> Dict:
    """记录一次AI判定的人工复核反馈"""
    records = _load()
    record = {
        "id": f"FB-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(records)+1:04d}",
        "inspection_id": inspection_id,
        "item_index": item_index,
        "facility": facility,
        "ai": {
            "violation": ai_violation,
            "confidence": ai_confidence,
            "hazard_code": ai_hazard_code,
        },
        "inspector": {
            "result": inspector_result,
            "note": inspector_note,
        },
        "correct": _is_correct(ai_violation, inspector_result),
        "recorded_at": datetime.now().isoformat(),
    }
    records.append(record)
    _save(records)

    # 累计纠正样本 > 50条时标记
    corrected = [r for r in records if not r["correct"]]
    return {
        "recorded": True,
        "feedback_id": record["id"],
        "total_samples": len(records),
        "corrected_samples": len(corrected),
    }


def get_accuracy_stats() -> Dict[str, Any]:
    """获取AI判定准确率统计"""
    records = _load()
    if not records:
        return {"total": 0, "accuracy": None, "trend": "insufficient_data", "message": "暂无反馈数据"}

    total = len(records)
    correct = sum(1 for r in records if r.get("correct", True))
    recent_20 = records[-20:]
    recent_correct = sum(1 for r in recent_20 if r.get("correct", True))

    accuracy = correct / total if total > 0 else 0
    recent_accuracy = recent_correct / len(recent_20) if recent_20 else 0

    # 趋势判断
    if recent_accuracy > accuracy + 0.05:
        trend = "improving"
    elif recent_accuracy < accuracy - 0.05:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 3),
        "recent_20_accuracy": round(recent_accuracy, 3),
        "trend": trend,
        "message": _trend_message(trend, accuracy),
    }


def get_prompt_examples_for_context() -> str:
    """从反馈中提取纠正样本，生成 prompt 示例文本（用于注入 Vision LLM）"""
    records = _load()
    corrected = [r for r in records if not r.get("correct", True)]
    if len(corrected) < 5:
        return ""

    # 取最近5个纠正样本
    examples = corrected[-5:]
    lines = ["\n## 历史纠正案例（请特别注意避免类似误判）"]
    for ex in examples:
        ai = ex.get("ai", {})
        insp = ex.get("inspector", {})
        lines.append(
            f"- {ex.get('facility', '')}: AI判定{'不合格' if ai.get('violation') else '合格'}"
            f"(置信度{ai.get('confidence',0):.0%}) "
            f"→ 监督员纠正为{insp.get('result', '?')}，备注: {insp.get('note', '')[:50]}"
        )
    return "\n".join(lines)


def _is_correct(ai_violation: bool | None, inspector_result: str) -> bool:
    """判断AI判定是否与监督员一致"""
    if ai_violation is None:
        return False  # AI无法判断算不算对
    ai_result = "fail" if ai_violation else "pass"
    return ai_result == inspector_result


def _trend_message(trend: str, accuracy: float) -> str:
    if trend == "improving":
        return f"AI准确率正在提升（当前 {accuracy:.0%}），反馈闭环生效中"
    if trend == "declining":
        return "AI准确率下降，建议检查模型配置或扩充训练样本"
    return f"AI准确率稳定在 {accuracy:.0%}"
