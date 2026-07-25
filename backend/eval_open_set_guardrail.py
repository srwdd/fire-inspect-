#!/usr/bin/env python3
"""开放集守护评测（2026-07-25 重写）。

旧版的两个问题：
1. 评测集 100% expect_refusal=True → precision 是空集上的退化值 1.000，零信息量
2. 把"检索返回空"当作拒答 → 根本没测 guardrail 模块本身

现在：
- 评测集混合应拒答/应接受样本（build_large_benchmark.py 生成，各 50%）
- 直接调用管线里真实的判决函数 app.services.guardrail.evaluate_guardrail
- 输出混淆矩阵、precision/recall/F1、AUROC（以 guardrail aggregate score 为分数），
  并附带旧口径（检索为空=拒答）作为对照基线
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.services.guardrail import evaluate_guardrail
from app.services.retriever import rule_retriever

DEFAULT_BENCHMARK = ROOT / "retrieval_benchmark_open_set_v2.json"
DEFAULT_JSON = ROOT / "experiments_open_set_guardrail_v2.json"


def load_cases(path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError("open-set benchmark must be a JSON list")
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        scene = str(item.get("scene") or "campus").strip() or "campus"
        if not query:
            continue
        out.append(
            {
                "name": str(item.get("name") or f"case_{len(out)}").strip(),
                "scene": scene,
                "query": query,
                "expect_refusal": bool(item.get("expect_refusal", True)),
            }
        )
    if not out:
        raise ValueError("no valid open-set cases")
    n_refuse = sum(1 for c in out if c["expect_refusal"])
    if n_refuse == 0 or n_refuse == len(out):
        raise ValueError(
            f"benchmark must mix refuse/accept cases, got refuse={n_refuse}/{len(out)}; "
            "regenerate with build_large_benchmark.py"
        )
    return out


def auroc(scored_labels: List[tuple[float, bool]]) -> Optional[float]:
    """Rank-based AUROC：分数越高越倾向拒答，label=True 为应拒答。"""
    pos = [s for s, label in scored_labels if label]
    neg = [s for s, label in scored_labels if not label]
    if not pos or not neg:
        return None
    wins = sum(1 for sp in pos for sn in neg if sp > sn)
    ties = sum(1 for sp in pos for sn in neg if sp == sn)
    return round((wins + 0.5 * ties) / (len(pos) * len(neg)), 4)


def confusion(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    tp = sum(1 for r in rows if r["predicted_refusal"] and r["expect_refusal"])
    fp = sum(1 for r in rows if r["predicted_refusal"] and not r["expect_refusal"])
    tn = sum(1 for r in rows if not r["predicted_refusal"] and not r["expect_refusal"])
    fn = sum(1 for r in rows if not r["predicted_refusal"] and r["expect_refusal"])
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "refusal_precision": round(precision, 4),
        "refusal_recall": round(recall, 4),
        "refusal_f1": round(f1, 4),
        "accuracy": round((tp + tn) / max(len(rows), 1), 4),
    }


def evaluate(cases: List[Dict[str, Any]], top_k: int) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    latency: List[float] = []

    for case in cases:
        begin = perf_counter()
        result = rule_retriever.retrieve_with_debug(case["query"], case["scene"], top_k=top_k)
        rules = result.get("rules", []) if isinstance(result, dict) else []
        debug = result.get("debug", {}) if isinstance(result, dict) else {}
        decision = evaluate_guardrail(case["query"], case["scene"], rules, debug)
        elapsed = (perf_counter() - begin) * 1000.0
        latency.append(elapsed)

        rows.append(
            {
                "name": case["name"],
                "scene": case["scene"],
                "query": case["query"],
                "expect_refusal": case["expect_refusal"],
                "predicted_refusal": bool(decision.should_refuse),
                "guardrail_score": decision.confidence,
                "guardrail_reasons": decision.reasons,
                "returned_count": len(rules),
                "correct": bool(decision.should_refuse) == case["expect_refusal"],
                "latency_ms": round(elapsed, 2),
            }
        )

    # 主口径：guardrail 模块判决
    metrics = confusion(rows)
    metrics["auroc"] = auroc([(r["guardrail_score"], r["expect_refusal"]) for r in rows])

    # 对照口径（旧评测方法）：检索返回空 = 拒答
    baseline_rows = [
        {**r, "predicted_refusal": r["returned_count"] == 0} for r in rows
    ]
    baseline_metrics = confusion(baseline_rows)

    # 阈值扫描：用 guardrail score 在不同阈值下的表现（辅助调 refusal_threshold）
    threshold_sweep = []
    for threshold in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        swept = [{**r, "predicted_refusal": r["guardrail_score"] >= threshold} for r in rows]
        m = confusion(swept)
        threshold_sweep.append({"threshold": threshold, **{k: m[k] for k in ("refusal_precision", "refusal_recall", "refusal_f1", "accuracy")}})

    sorted_latency = sorted(latency)
    p95_idx = int(round(0.95 * (len(sorted_latency) - 1))) if sorted_latency else 0
    return {
        "benchmark": str(DEFAULT_BENCHMARK.name),
        "case_count": len(rows),
        "refuse_cases": sum(1 for r in rows if r["expect_refusal"]),
        "accept_cases": sum(1 for r in rows if not r["expect_refusal"]),
        "guardrail": metrics,
        "empty_retrieval_baseline": baseline_metrics,
        "threshold_sweep": threshold_sweep,
        "avg_latency_ms": round(mean(latency), 2) if latency else 0.0,
        "p95_latency_ms": round(sorted_latency[p95_idx], 2) if sorted_latency else 0.0,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate open-set guardrail with mixed refuse/accept benchmark.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()

    cases = load_cases(args.benchmark)
    report = evaluate(cases, top_k=args.top_k)

    g = report["guardrail"]
    b = report["empty_retrieval_baseline"]
    print(f"\n[guardrail module]  cases={report['case_count']} (refuse={report['refuse_cases']}, accept={report['accept_cases']})")
    print(f"  precision={g['refusal_precision']:.4f}  recall={g['refusal_recall']:.4f}  f1={g['refusal_f1']:.4f}  auroc={g['auroc']}")
    print(f"  confusion: tp={g['tp']} fp={g['fp']} tn={g['tn']} fn={g['fn']}")
    print(f"[empty-retrieval baseline]  precision={b['refusal_precision']:.4f}  recall={b['refusal_recall']:.4f}")
    print("[threshold sweep]")
    for row in report["threshold_sweep"]:
        print(f"  t={row['threshold']:.1f}  p={row['refusal_precision']:.4f}  r={row['refusal_recall']:.4f}  f1={row['refusal_f1']:.4f}")

    args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved JSON report to: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
