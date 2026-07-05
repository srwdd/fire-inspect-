"""报告导出服务 — HTML(可打印PDF) + Excel (Phase P0)"""
import io
from datetime import datetime

from app.core.checklist_engine import checklist_engine
from app.db.storage import get_inspection, get_findings


def generate_html_report(inspection_id: str) -> str:
    """生成可打印的 HTML 报告，浏览器 Ctrl+P → 保存PDF"""
    insp = get_inspection(inspection_id)
    if not insp:
        return "<p>检查记录不存在</p>"

    findings = get_findings(inspection_id)
    fails = [f for f in findings if f.get("result") == "fail"]
    passes = [f for f in findings if f.get("result") == "pass"]
    assessment = checklist_engine.calculate_assessment(findings)

    items_html = ""
    for i, f in enumerate(findings):
        result_label = {"pass": "✅ 合格", "fail": "❌ 不合格", "na": "⊘ 不涉及"}.get(f.get("result", ""), "?" )
        result_color = "#f5222d" if f.get("result") == "fail" else ("#52c41a" if f.get("result") == "pass" else "#999")
        items_html += f"""
        <tr>
            <td style="text-align:center">{i+1}</td>
            <td>{f.get('facility', '')}</td>
            <td>{f.get('check_point', '')}</td>
            <td style="color:{result_color};font-weight:bold;text-align:center">{result_label}</td>
            <td style="font-size:12px;color:#666">{f.get('note', '')}</td>
        </tr>"""

    color_map = {"red": "高风险", "orange": "较高风险", "yellow": "一般风险", "green": "低风险"}
    color_hex = {"red": "#f5222d", "orange": "#fa8c16", "yellow": "#faad14", "green": "#52c41a"}

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>消防监督检查记录表</title>
<style>
@page {{ size: A4; margin: 15mm; }}
body {{ font-family: 'SimSun','宋体',serif; font-size:14px; color:#333; line-height:1.8; }}
h1 {{ text-align:center; font-size:20px; margin-bottom:4px; }}
.subtitle {{ text-align:center; font-size:12px; color:#999; margin-bottom:20px; }}
table {{ width:100%; border-collapse:collapse; margin:12px 0; }}
th,td {{ border:1px solid #ddd; padding:8px 10px; text-align:left; }}
th {{ background:#f5f5f5; font-weight:bold; }}
.info-table td {{ width:50%; }}
.score-box {{ text-align:center; padding:20px; border-radius:8px; margin:16px 0; font-size:18px; }}
.signature {{ margin-top:40px; display:flex; justify-content:space-between; }}
.signature div {{ width:45%; border-top:1px solid #333; padding-top:8px; text-align:center; }}
@media print {{ .no-print {{ display:none; }} }}
</style></head>
<body>
<h1>消防监督检查记录表</h1>
<div class="subtitle">编号: {inspection_id} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>

<table class="info-table">
<tr><th>场所名称</th><td>{insp.get('venue_name', '')}</td><th>场所类型</th><td>{insp.get('venue_type', '')}</td></tr>
<tr><th>检查地址</th><td>{insp.get('location', '')}</td><th>检查日期</th><td>{insp.get('started_at', '')[:10]}</td></tr>
<tr><th>检查人</th><td>{insp.get('inspector', '')}</td><th>检查模式</th><td>{'复查' if insp.get('mode')=='recheck' else '首次检查'}</td></tr>
</table>

<div class="score-box" style="background:{color_hex.get(assessment['color'],'#f5f5f5')};color:#fff;">
  综合评分: {assessment['score']} 分 — {color_map.get(assessment['color'], '')}
</div>

<table>
<tr><th style="width:5%">序号</th><th style="width:18%">检查部位</th><th style="width:35%">检查要点</th><th style="width:10%">判定</th><th style="width:32%">备注</th></tr>
{items_html}
</table>

<div style="margin-top:20px;font-weight:bold;">
  合格: {len(passes)} 项 | 不合格: {len(fails)} 项 | 总计: {len(findings)} 项
</div>

<div class="signature">
<div>检查人签字</div><div>被检查单位负责人签字</div>
</div>
</body></html>"""


def generate_excel_data(inspection_id: str) -> bytes:
    """生成 Excel 数据 (CSV格式，Excel可直接打开)"""
    import csv
    insp = get_inspection(inspection_id)
    if not insp:
        return b""

    findings = get_findings(inspection_id)
    output = io.StringIO()
    writer = csv.writer(output)

    # 表头
    writer.writerow(["消防监督检查记录表"])
    writer.writerow(["编号", inspection_id])
    writer.writerow(["场所", insp.get("venue_name", ""), "类型", insp.get("venue_type", "")])
    writer.writerow(["地址", insp.get("location", ""), "日期", insp.get("started_at", "")[:10]])
    writer.writerow(["检查人", insp.get("inspector", ""), "模式", "复查" if insp.get("mode") == "recheck" else "首次"])
    writer.writerow([])
    writer.writerow(["序号", "检查部位", "检查要点", "类别", "严重程度", "判定", "备注"])

    for i, f in enumerate(findings):
        writer.writerow([
            i + 1,
            f.get("facility", ""),
            f.get("check_point", ""),
            f.get("category", ""),
            f.get("severity", ""),
            f.get("result", ""),
            f.get("note", ""),
        ])

    # 增加BOM使Excel正确识别中文
    return ("﻿" + output.getvalue()).encode("utf-8")
