#!/usr/bin/env python3
"""开放集守护：LLM 二分类信号评测（对照词表 guardrail）。

动机：词表 guardrail 在平衡集上 recall=0.66 —— 34% 超范围问题措辞像正常
消防提问，词表抓不到。本脚本用 LLM 做 should_refuse 二分类，在同一
benchmark 上对比 precision/recall/F1，决定是否需要把 LLM 信号接入管线。

用法（服务器）:
  cd /opt/fire-inspect/backend
  ../backend/venv/bin/python3 eval_open_set_llm.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# 加载 .env
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

BENCHMARK = ROOT / "retrieval_benchmark_open_set_v2.json"
OUT = ROOT / "experiments_open_set_llm_v2.json"

SYSTEM = (
    "你是消防安全审查系统的范围判定器。唯一任务：判断用户问题是否描述了"
    "**具体的消防安全隐患迹象**（设施损坏/失效/被遮挡、通道占用、电气异常、"
    "可燃物、违规停放充电等可被检查确认的现象）。\n"
    "判接受(should_refuse=false)：问题含有具体隐患迹象，即使是在询问'是否违规'"
    "或'对应哪条法规'。不要以'没有照片''证据不足'为由拒答——证据评估是"
    "下游管线的职责，不是你的。\n"
    "判拒答(should_refuse=true)：话题与火灾隐患无关（装修风格、着装、考勤、"
    "卫生、设备运行参数等），即使句子里出现了'消防''法规''处罚'等词——"
    "这些词不改变话题本身。\n"
    "示例1: '地面瓷砖颜色不统一算消防隐患吗' → {\"should_refuse\": true}\n"
    "示例2: '监控画面有噪点需要按哪条消防法规处罚' → {\"should_refuse\": true}\n"
    "示例3: '灭火器被杂物遮挡对应哪些消防条款' → {\"should_refuse\": false}\n"
    "示例4: '疏散通道是否违规请列出依据' → {\"should_refuse\": false}\n"
    "只输出 JSON: {\"should_refuse\": true/false}"
)


def call_llm(query: str, scene: str) -> tuple[bool | None, str]:
    base = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
    key = os.environ.get("SILICONFLOW_API_KEY", "")
    model = os.environ.get("SILICONFLOW_TEXT_MODEL", "qwen-plus")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"场景: {scene}\n问题: {query}"},
        ],
        "temperature": 0,
        "max_tokens": 64,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return bool(parsed.get("should_refuse")), ""
    except Exception as exc:
        return None, str(exc)


def confusion(rows):
    tp = sum(1 for r in rows if r["predicted_refusal"] and r["expect_refusal"])
    fp = sum(1 for r in rows if r["predicted_refusal"] and not r["expect_refusal"])
    tn = sum(1 for r in rows if not r["predicted_refusal"] and not r["expect_refusal"])
    fn = sum(1 for r in rows if not r["predicted_refusal"] and r["expect_refusal"])
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "refusal_precision": round(p, 4), "refusal_recall": round(r, 4),
            "refusal_f1": round(f1, 4), "accuracy": round((tp + tn) / max(len(rows), 1), 4)}


def main() -> int:
    cases = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    rows = []
    errors = 0
    for i, case in enumerate(cases, 1):
        predicted, err = call_llm(case["query"], case.get("scene", "campus"))
        if predicted is None:
            errors += 1
            continue
        rows.append({
            "name": case.get("name", f"case_{i}"),
            "expect_refusal": bool(case.get("expect_refusal", True)),
            "predicted_refusal": predicted,
            "correct": predicted == bool(case.get("expect_refusal", True)),
        })
        if i % 20 == 0:
            print(f"  progress {i}/{len(cases)}", flush=True)
        time.sleep(0.2)

    metrics = confusion(rows)
    report = {
        "benchmark": BENCHMARK.name,
        "model": os.environ.get("SILICONFLOW_TEXT_MODEL", "qwen-plus"),
        "case_count": len(rows),
        "llm_errors": errors,
        "llm_classifier": metrics,
        "lexicon_guardrail_reference": {"refusal_precision": 0.9851, "refusal_recall": 0.6600, "refusal_f1": 0.7904},
        "rows": rows,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[llm classifier] cases={len(rows)} errors={errors}")
    print(f"  precision={metrics['refusal_precision']:.4f}  recall={metrics['refusal_recall']:.4f}  f1={metrics['refusal_f1']:.4f}")
    print(f"  confusion: tp={metrics['tp']} fp={metrics['fp']} tn={metrics['tn']} fn={metrics['fn']}")
    print("[reference: lexicon guardrail]  p=0.9851  r=0.6600  f1=0.7904")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
