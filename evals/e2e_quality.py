#!/usr/bin/env python3
"""端到端生成质量评测（2026-07-26 新增）。

此前所有指标只测检索层（规则命中），two-hop 的"证据约束推理"收益从未被
直接验证。本脚本用 evals/eval_dataset.json 的 50 条人工编写用例，走真实
管线的文本路径（合成 stage1 → 检索 → guardrail → 真实 stage2 prompt + LLM），
直接测量生成层质量：

- 风险分级准确率：overall_risk 与人工标注 expected_judgment 的一致性
  （严格口径 fail→danger、pass→safe；宽松口径 fail→danger|warning）
- 引用忠实率：stage2 输出的 citations (article, source) 是否全部来自
  实际检索到的规则（白名单外 = 幻觉引用）
- 法条召回：expected_regulation 是否出现在检索结果（检索层）和
  最终引用（生成层）中

注意：stage1 是文本合成（VLM 视觉层不在本评测范围，需要真实图片集）。
用法（服务器）: cd /opt/fire-inspect/backend && venv/bin/python3 ../evals/e2e_quality.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from statistics import mean

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

# 加载 .env
_env = BACKEND / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from app.core.config import settings
from app.services.analyzer import analyzer_service
from app.services.guardrail import evaluate_guardrail
from app.services.retriever import rule_retriever

DATASET = Path(__file__).resolve().parent / "eval_dataset.json"
OUT = BACKEND / "experiments_e2e_quality_v1.json"


def _norm_reg(text: str) -> str:
    """法条编号匹配归一化：GB50444 vs GB 50444-2008 的空格差异。
    2026-07-26：未归一化时法条召回被低估到 0.08（字符串假阴性）。"""
    return "".join(str(text or "").split()).lower()


def risk_matches(predicted: str, expected_judgment: str, strict: bool) -> bool:
    p = (predicted or "").lower()
    if expected_judgment == "fail":
        return p == "danger" if strict else p in ("danger", "warning")
    # pass
    return p == "safe"


def main() -> int:
    api_key = os.environ.get("SILICONFLOW_API_KEY", "")
    if not api_key:
        print("SILICONFLOW_API_KEY not set; stage2 LLM unavailable")
        return 1

    suite = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = suite["test_cases"]
    rows = []

    for i, case in enumerate(cases, 1):
        text = case["input"]
        facility = case.get("facility", "")
        scene = case.get("scene", "office")
        expected_judgment = case.get("expected_judgment", "fail")
        expected_regs = case.get("expected_regulation", [])
        if isinstance(expected_regs, str):
            expected_regs = [expected_regs]

        stage1_result = {
            "scene_observation": text,
            "suspected_hazards": [facility] if facility else [],
            "keywords": [facility] if facility else [],
        }
        retrieval_query = " ".join([scene, text, facility]).strip()

        t0 = time.time()
        retrieval = rule_retriever.retrieve_with_debug(query=retrieval_query, scene=scene, top_k=settings.RAG_TOP_K)
        rules = retrieval["rules"]
        debug = retrieval["debug"]
        guard = evaluate_guardrail(retrieval_query, scene, rules, debug)

        # 检索层法条召回
        retrieved_src = _norm_reg(" ".join(str(r.get("source", "")) + str(r.get("article", "")) for r in rules))
        expected_norm = [_norm_reg(exp) for exp in expected_regs]
        reg_hit_retrieval = any(exp in retrieved_src for exp in expected_norm) if expected_norm else None

        row = {
            "id": case.get("id", f"E{i:03d}"),
            "facility": facility,
            "expected_judgment": expected_judgment,
            "rules_returned": len(rules),
            "guardrail_refuse": guard.should_refuse,
            "reg_hit_retrieval": reg_hit_retrieval,
        }

        if guard.should_refuse or not rules:
            row.update({"predicted_risk": "guarded", "strict_ok": None, "lenient_ok": None,
                        "citations": 0, "citations_faithful": None, "reg_hit_citation": None})
        else:
            prompt = analyzer_service._build_stage2_prompt(scene, stage1_result, rules)
            call = analyzer_service._chat_completion(
                api_key=api_key,
                model=analyzer_service.text_model,
                messages=[
                    {"role": "system", "content": "You are a strict fire-safety compliance assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=700,
            )
            parsed = analyzer_service._extract_json(call.get("raw", "")) if call.get("ok") else None
            if parsed is None:
                row.update({"predicted_risk": "parse_error", "strict_ok": None, "lenient_ok": None,
                            "citations": 0, "citations_faithful": None, "reg_hit_citation": None,
                            "stage2_error": call.get("error", "parse_failed")})
            else:
                predicted = str(parsed.get("overall_risk", "")).lower()
                citations = parsed.get("citations") or []
                # 白名单校验（与 analyzer 一致的忠实率口径）
                whitelist = {(str(r.get("article", "")), str(r.get("source", ""))) for r in rules}
                faithful = 0
                hallucinated = []
                for c in citations:
                    pair = (str(c.get("article", "")), str(c.get("source", "")))
                    if pair in whitelist:
                        faithful += 1
                    else:
                        hallucinated.append(pair)
                cite_src = _norm_reg(" ".join(str(c.get("source", "")) + str(c.get("article", "")) for c in citations))
                row.update({
                    "predicted_risk": predicted,
                    "strict_ok": risk_matches(predicted, expected_judgment, strict=True),
                    "lenient_ok": risk_matches(predicted, expected_judgment, strict=False),
                    "citations": len(citations),
                    "citations_faithful": faithful,
                    "citations_hallucinated": len(hallucinated),
                    "hallucinated_pairs": hallucinated[:3],
                    "reg_hit_citation": (any(exp in cite_src for exp in expected_norm) if expected_norm else None),
                })

        row["latency_ms"] = round((time.time() - t0) * 1000, 1)
        rows.append(row)
        if i % 10 == 0:
            print(f"  progress {i}/{len(cases)}", flush=True)
        time.sleep(0.2)

    judged = [r for r in rows if r.get("strict_ok") is not None]
    guarded = [r for r in rows if r.get("predicted_risk") == "guarded"]
    errors = [r for r in rows if r.get("predicted_risk") == "parse_error"]
    cited = [r for r in judged if r.get("citations")]

    def rate(items, key):
        vals = [x[key] for x in items if x.get(key) is not None]
        return round(mean(1.0 if x else 0.0 for x in vals), 4) if vals else None

    summary = {
        "case_count": len(rows),
        "stage2_judged": len(judged),
        "guarded_or_no_rules": len(guarded),
        "parse_errors": len(errors),
        "risk_accuracy_strict": rate(judged, "strict_ok"),
        "risk_accuracy_lenient": rate(judged, "lenient_ok"),
        "citation_faithful_rate": rate(cited, "citations_faithful") if cited else None,
        "total_citations": sum(r.get("citations", 0) for r in judged),
        "total_hallucinated": sum(r.get("citations_hallucinated", 0) for r in judged),
        "reg_hit_retrieval_rate": rate(rows, "reg_hit_retrieval"),
        "reg_hit_citation_rate": rate(judged, "reg_hit_citation"),
        "avg_latency_ms": round(mean(r["latency_ms"] for r in rows), 1),
    }
    report = {"dataset": "evals/eval_dataset.json", "summary": summary, "rows": rows}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n[e2e generation quality]")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
