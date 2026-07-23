#!/usr/bin/env python3
"""火准·AI评测脚本 — 运行方法: cd /opt/fire-inspect && backend/venv/bin/python3 evals/run_eval.py"""
import json, os, sys, time

sys.path.insert(0, "backend")
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")

from app.services.regulation_search import search_all

def run_eval():
    with open("evals/eval_dataset.json", "r", encoding="utf-8") as f:
        suite = json.load(f)

    cases = suite["test_cases"]
    results = {"total": len(cases), "passed": 0, "failed": 0, "details": []}

    for tc in cases:
        all_results = search_all(tc["input"], facility=tc.get("facility", ""), top_k=12)
        rules = all_results.get("regulations", [])
        solutions = all_results.get("solutions", [])

        # 检查1: 法规召回 — 是否匹配到相关法规
        expected_regs = tc.get("expected_regulation", [])
        if isinstance(expected_regs, str):
            expected_regs = [expected_regs]
        reg_ok = any(
            any(exp in r.get("source", "") for exp in expected_regs)
            or any(kw in (r.get("title","") + r.get("check_point","")).lower()
                   for kw in tc.get("expected_keywords", []))
            for r in rules
        )

        # 检查2: 方案匹配 — 是否有对应整改方案
        sol_ok = len(solutions) > 0

        # 综合判定
        passed = reg_ok and sol_ok
        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1

        results["details"].append({
            "id": tc["id"],
            "input": tc["input"],
            "expected_judgment": tc["expected_judgment"],
            "regulation_recall": reg_ok,
            "solution_match": sol_ok,
            "passed": passed,
            "top_rule": rules[0].get("source","") + " " + rules[0].get("title","")[:60] if rules else "无结果",
            "top_solution": solutions[0].get("immediate_action","")[:60] if solutions else "无方案",
        })

    # 输出报告
    acc = results["passed"] / results["total"] * 100 if results["total"] > 0 else 0
    print(f"\n{'='*60}")
    print(f"  火准·AI评测报告")
    print(f"  通过: {results['passed']}/{results['total']} ({acc:.1f}%)")
    print(f"{'='*60}")

    for d in results["details"]:
        icon = "✓" if d["passed"] else "✗"
        print(f"  {icon} {d['id']} | 法规:{'✓' if d['regulation_recall'] else '✗'} 方案:{'✓' if d['solution_match'] else '✗'} | {d['input'][:40]}")
        if not d["passed"]:
            print(f"     法规命中: {d['top_rule'][:80]}")
            print(f"     方案命中: {d['top_solution'][:80]}")

    # 分类统计
    by_facility = {}
    for d in results["details"]:
        tc = next(c for c in cases if c["id"] == d["id"])
        fac = tc.get("facility", "其他")
        if fac not in by_facility:
            by_facility[fac] = {"total": 0, "passed": 0}
        by_facility[fac]["total"] += 1
        if d["passed"]:
            by_facility[fac]["passed"] += 1

    print(f"\n{'='*60}")
    print(f"  按设施类型统计")
    print(f"{'='*60}")
    for fac, stats in sorted(by_facility.items()):
        pct = stats["passed"] / stats["total"] * 100
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        print(f"  {fac:<12} {bar} {stats['passed']}/{stats['total']} ({pct:.0f}%)")

    return results

if __name__ == "__main__":
    run_eval()
