#!/usr/bin/env python3
"""
火鉴·警鉴 — 定期网络案例采集器
策略：搜索 → 提取 → 去重 → 审核标记 → 入库
频率：每周运行一次（cron: 0 9 * * 1）
"""
import json, os, re, sys
from datetime import datetime, date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent if "__file__" in dir() else Path("/opt/fire-inspect")
CASES_FILE = BASE / "fire_cases.json"
COLLECT_LOG = BASE / "evals" / "collect_log.json"

# ═══════════════════════════════════════════════
# 1. 信源配置 — 只采集权威来源
# ═══════════════════════════════════════════════
SOURCES = {
    "应急管理部消防救援局": {
        "url": "https://www.119.gov.cn",
        "type": "national",
        "reliability": "high",
        "search_terms": ["典型执法案例", "行政处罚", "火灾隐患曝光", "重大火灾隐患"],
    },
    "各省消防救援总队": {
        "url_pattern": "https://{province}.119.gov.cn",
        "type": "provincial",
        "reliability": "high",
        "provinces": ["jx", "gd", "js", "hn", "bj", "sh", "zj"],
    },
    "信用中国": {
        "url": "https://www.creditchina.gov.cn",
        "type": "government",
        "reliability": "high",
        "search_terms": ["消防", "行政处罚", "隐患"],
    },
}

# ═══════════════════════════════════════════════
# 2. 采集逻辑 — 基于 WebSearch + 结构化提取
# ═══════════════════════════════════════════════
def collect_from_websearch():
    """
    使用 WebSearch 搜索近期消防执法案例
    由于无法在脚本中直接调用 WebSearch，此函数生成搜索提示
    供 AI Agent 在运行时执行搜索
    """
    queries = [
        "消防监督检查 行政处罚 案例 2026 site:gov.cn",
        "重大火灾隐患 挂牌督办 2026 消防安全",
        "消防执法 典型案例 公示 site:119.gov.cn 2026",
        "火灾隐患曝光 单位 罚款 消防设施 2026",
    ]
    return queries


def extract_case_from_text(text: str, source: str) -> dict:
    """从原始文本中提取结构化案例"""
    case = {
        "id": "",
        "facility": "",
        "category": "",
        "finding": "",
        "finding_keywords": [],
        "venue_type": "",
        "severity": "normal",
        "regulation_refs": [],
        "cause": "",
        "consequence": "",
        "photo_features": "",
        "typical_scene": "",
        "created": str(date.today()),
        "source": source,
        "reviewed": False,  # 标记待人工审核
    }

    # 设施识别
    facility_patterns = {
        "灭火器": "灭火器",
        "消火栓|消防栓": "消火栓",
        "报警|探测器|烟感": "火灾报警系统",
        "喷淋|自动喷水": "自动喷水灭火系统",
        "防火门|卷帘": "防火门",
        "安全出口|疏散|楼梯": "疏散设施",
        "电气|电线|线路|配电": "电气线路",
        "彩钢板|夹芯板|泡沫": "建筑材料",
        "燃气|煤气|液化气": "燃气管道",
        "控制室|值班|消控室": "消防控制室",
        "电动车|充电": "电动自行车",
    }
    for pattern, facility in facility_patterns.items():
        if re.search(pattern, text):
            case["facility"] = facility
            case["category"] = facility
            break

    # 关键词提取
    case["finding_keywords"] = [w for w in re.findall(r'[一-鿿]{2,4}', text[:200]) if len(w) >= 2][:5]

    # 严重等级判定
    if re.search(r'重大火灾隐患|查封|刑事|拘留|伤亡', text):
        case["severity"] = "critical"
    elif re.search(r'罚款|处罚|责令|逾期', text):
        case["severity"] = "high"
    elif re.search(r'整改|警告|限期', text):
        case["severity"] = "medium"

    # 法条提取
    case["regulation_refs"] = re.findall(r'(?:消防法|GB\s*\d+[\.-]\d+|第[零一二三四五六七八九十百千]+条)', text)

    # 金额提取
    amounts = re.findall(r'罚款?\s*(\d+\.?\d*)\s*万?元?', text)
    penalty = ""
    if amounts:
        penalty = "罚款" + amounts[0] + ("万元" if "万" in text else "元")

    case["consequence"] = penalty + ("；" + re.search(r'(责令[^。；]+|临时查封[^。；]+|挂牌督办[^。；]+)', text).group(1) if re.search(r'(责令[^。；]+|临时查封[^。；]+|挂牌督办[^。；]+)', text) else "")
    case["cause"] = text[:100]
    case["finding"] = text[:150]

    return case


# ═══════════════════════════════════════════════
# 3. 去重引擎
# ═══════════════════════════════════════════════
def deduplicate(new_cases: list, existing_cases: list) -> list:
    """基于 finding 文本相似度去重"""
    existing_texts = set()
    for c in existing_cases:
        f = c.get("finding", "")
        # 取前40字做指纹
        existing_texts.add(f[:40])
        # 也存前20字的简化版
        existing_texts.add(re.sub(r'[，。；、\s]', '', f)[:20])

    unique = []
    for c in new_cases:
        f = c.get("finding", "")
        fingerprint = f[:40]
        simplified = re.sub(r'[，。；、\s]', '', f)[:20]
        if fingerprint not in existing_texts and simplified not in existing_texts:
            unique.append(c)
            existing_texts.add(fingerprint)

    return unique


# ═══════════════════════════════════════════════
# 4. 入库 + 日志
# ═══════════════════════════════════════════════
def save_cases(new_cases: list, dry_run: bool = True):
    """保存案例到警鉴库"""
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing = data.get("cases", [])
    unique = deduplicate(new_cases, existing)

    if dry_run:
        print(f"\n[DRY RUN] 发现 {len(new_cases)} 条，去重后 {len(unique)} 条新案例（未实际写入）")
        for c in unique[:5]:
            print(f"  - {c['facility']}: {c['finding'][:60]} [{c['source'][:30]}]")
        return unique

    # 分配ID
    max_id = 0
    for c in existing:
        try:
            num = int(c["id"].replace("CR", "").replace("CAUTO", "").replace("C0", "").replace("C", ""))
            if num > max_id:
                max_id = num
        except:
            pass

    for c in unique:
        max_id += 1
        c["id"] = f"CR{max_id:03d}"

    data["cases"].extend(unique)
    data["knowledge_base"]["built_at"] = str(date.today())

    with open(CASES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 记录日志
    log_entry = {
        "date": str(date.today()),
        "collected": len(new_cases),
        "deduplicated": len(unique),
        "total_cases": len(data["cases"]),
        "new_ids": [c["id"] for c in unique],
    }

    log_path = COLLECT_LOG
    logs = []
    if log_path.exists():
        logs = json.loads(log_path.read_text())
    logs.append(log_entry)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(logs, ensure_ascii=False, indent=2))

    print(f"\n[入库] {len(unique)}/{len(new_cases)} 条新案例 (总计 {len(data['cases'])} 条)")
    return unique


# ═══════════════════════════════════════════════
# 5. 命令行入口
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="火鉴·警鉴 — 网络案例采集器")
    parser.add_argument("--dry-run", action="store_true", default=True, help="预览模式（默认）")
    parser.add_argument("--save", action="store_true", help="实际写入（需人工确认）")
    parser.add_argument("--source", type=str, help="指定来源URL")
    args = parser.parse_args()

    print("=" * 50)
    print("  火鉴·警鉴 — 案例采集器")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  当前案例库: {CASES_FILE}")
    print("=" * 50)

    # 显示采集查询
    queries = collect_from_websearch()
    print("\n📋 推荐搜索查询（由 AI Agent 执行）:")
    for i, q in enumerate(queries, 1):
        print(f"  {i}. {q}")

    print("\n💡 用法:")
    print("  1. AI Agent 执行以上搜索查询")
    print("  2. 从搜索结果中提取案例文本")
    print("  3. 运行: python3 collect_cases.py --save --source '<来源>'")
    print("  4. 人工审核 review=true 的案例后确认入库")
