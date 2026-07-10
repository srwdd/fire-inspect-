"""报告导出服务 v2 — 美化版 HTML(可打印PDF) + Excel (Phase P1)"""
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
    na_items = [f for f in findings if f.get("result") == "na"]
    assessment = checklist_engine.calculate_assessment(findings)

    # ── 按类别分组 ──
    categories_order = ["消防管理", "技术条件", "设施完好"]
    grouped = {}
    for f in findings:
        cat = f.get("category", "其他")
        grouped.setdefault(cat, []).append(f)

    items_html = ""
    seq = 0
    for cat in categories_order:
        if cat not in grouped:
            continue
        items_html += f'<tr class="cat-header"><td colspan="6">{cat}（{len(grouped[cat])} 项）</td></tr>'
        for f in grouped[cat]:
            seq += 1
            result = f.get("result", "")
            result_label = {"pass": "✅ 合格", "fail": "❌ 不合格", "na": "⊘ 不涉及"}.get(result, "?")
            result_cls = "fail" if result == "fail" else ("pass" if result == "pass" else "na")
            severity = f.get("severity", "")
            sev_badge = ""
            if result == "fail" and f.get("is_mandatory"):
                sev_badge = '<span class="badge badge-danger">A类</span>'
            elif result == "fail" and severity == "important":
                sev_badge = '<span class="badge badge-warn">B类</span>'
            note = (f.get("note") or "").replace("<", "&lt;").replace(">", "&gt;")
            items_html += f"""<tr class="row-{result_cls}">
                <td class="col-seq">{seq}</td>
                <td class="col-facility">{f.get('facility', '')}</td>
                <td class="col-checkpoint">{f.get('check_point', '')}</td>
                <td class="col-severity">{sev_badge}</td>
                <td class="col-result">{result_label}</td>
                <td class="col-note">{note}</td>
            </tr>"""

    # ── 评分卡 ──
    from math import radians, sin, cos, sqrt, atan2
    color_hex = {"red": "#dc2626", "orange": "#ea580c", "yellow": "#ca8a04", "green": "#16a34a"}
    color_label = {"red": "高风险 🔴", "orange": "较高风险 🟠", "yellow": "一般风险 🟡", "green": "低风险 🟢"}
    score_color = color_hex.get(assessment.get("color", "green"), "#16a34a")
    total = len(findings)
    fail_pct = round(len(fails) / total * 100) if total > 0 else 0
    pass_pct = round(len(passes) / total * 100) if total > 0 else 0

    # ── QR Code 指向在线报告 ──
    qr_url = f"https://ai-bang.top/inspect/web/?report={inspection_id}"
    gen_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>消防监督检查记录表 — {inspection_id}</title>
<style>
@page {{ size: A4; margin: 12mm 15mm; }}
* {{ box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', 'SimSun', serif;
  font-size: 13px; color: #1a1a1a; line-height: 1.7;
  max-width: 210mm; margin: 0 auto; padding: 0;
  min-height: 277mm; /* A4 content height */
}}

/* ── 签章区 ── */
.signature-area {{
  margin-top: 32px; display: flex; justify-content: space-between;
  padding-top: 16px; border-top: 1px dashed #ccc;
}}
.signature-item {{
  text-align: center; min-width: 120px;
}}
.signature-item .label {{ font-size: 12px; color: #555; margin-bottom: 36px; }}
.signature-item .date {{ font-size: 11px; color: #999; }}

/* ── 页脚 ── */
.page-footer {{
  margin-top: 24px; padding-top: 8px; border-top: 1px solid #e5e5e5;
  font-size: 10px; color: #999; text-align: center;
}}
.page-footer span {{ margin: 0 8px; }}

@media print {{
  .no-print {{ display: none; }}
  body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
}}
}}

/* ── 页头 ── */
.red-header {{
  text-align: center; border-bottom: 2px solid #dc2626;
  padding-bottom: 10px; margin-bottom: 10px;
}}
.red-header .org-name {{
  font-size: 16px; font-weight: 700; color: #dc2626;
  letter-spacing: 4px; margin: 0;
}}
.red-header .doc-title {{
  font-size: 20px; font-weight: 700; color: #1a1a1a;
  letter-spacing: 3px; margin: 6px 0 0;
}}
.header {{
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 8px; margin-bottom: 12px;
}}
.header-left .report-no {{ font-size: 11px; color: #666; }}
.header-right {{ text-align: right; }}
.header-right .qr-box {{ margin-top: 0; }}
.header-right .qr-box img {{ width: 56px; height: 56px; }}
.header-right .qr-label {{ font-size: 8px; color: #999; }}

/* ── 信息表 ── */
.info-grid {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 0;
  border: 1px solid #d4d4d4; margin-bottom: 16px;
}}
.info-item {{
  display: flex; border-bottom: 1px solid #e5e5e5;
}}
.info-item:nth-child(odd) {{ border-right: 1px solid #e5e5e5; }}
.info-label {{
  background: #fafafa; padding: 6px 10px; font-weight: 600;
  font-size: 12px; color: #555; min-width: 72px; white-space: nowrap;
}}
.info-value {{ padding: 6px 10px; font-size: 13px; flex: 1; }}

/* ── 评分卡 ── */
.score-section {{ margin: 16px 0; }}
.score-cards {{ display: flex; gap: 10px; margin-bottom: 12px; }}
.score-card {{
  flex: 1; text-align: center; padding: 12px 8px; border-radius: 6px;
  border: 1px solid #e5e5e5;
}}
.score-card .num {{ font-size: 28px; font-weight: 700; }}
.score-card .label {{ font-size: 11px; color: #666; margin-top: 2px; }}
.score-card.pass .num {{ color: #16a34a; }}
.score-card.fail .num {{ color: #dc2626; }}
.score-card.na-card .num {{ color: #999; }}

.score-bar-wrap {{
  display: flex; border-radius: 8px; overflow: hidden; height: 28px;
  margin-bottom: 6px;
}}
.score-bar-pass {{ background: #16a34a; transition: width .3s; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 11px; font-weight: 600; }}
.score-bar-fail {{ background: #dc2626; transition: width .3s; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 11px; font-weight: 600; }}
.score-bar-na {{ background: #d4d4d4; transition: width .3s; }}
.score-legend {{ font-size: 10px; color: #999; text-align: right; }}

.assessment-box {{
  background: {score_color}; color: #fff; text-align: center;
  padding: 10px; border-radius: 6px; font-size: 15px; font-weight: 700;
  margin-top: 8px;
}}

/* ── 检查明细表 ── */
table.findings {{
  width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 12px;
}}
table.findings th {{
  background: #1a1a1a; color: #fff; padding: 8px 6px; text-align: center;
  font-weight: 600; font-size: 11px;
}}
table.findings td {{
  padding: 6px; border-bottom: 1px solid #e5e5e5; vertical-align: top;
}}
.cat-header td {{
  background: #fef2f2; font-weight: 700; font-size: 13px; color: #991b1b;
  padding: 8px 10px; border-bottom: 2px solid #fecaca;
}}
.row-fail {{ background: #fff5f5; }}
.row-fail:hover {{ background: #fee2e2; }}
.row-pass {{ }}
.row-na {{ color: #999; }}

.col-seq {{ width: 36px; text-align: center; color: #999; font-size: 11px; }}
.col-facility {{ width: 14%; font-weight: 500; }}
.col-checkpoint {{ width: 34%; }}
.col-severity {{ width: 50px; text-align: center; }}
.col-result {{ width: 70px; text-align: center; font-weight: 600; }}
.col-note {{ width: 22%; font-size: 11px; color: #666; }}

.badge {{
  display: inline-block; padding: 1px 6px; border-radius: 3px;
  font-size: 10px; font-weight: 700; color: #fff;
}}
.badge-danger {{ background: #dc2626; }}
.badge-warn {{ background: #ea580c; }}

/* ── 签名区 ── */
.signature-area {{
  margin-top: 40px; display: flex; justify-content: space-between; gap: 40px;
}}
.signature-block {{
  flex: 1; text-align: center;
}}
.signature-line {{
  border-bottom: 1px solid #1a1a1a; margin-bottom: 6px; height: 40px;
}}
.signature-block .sig-label {{ font-size: 12px; color: #555; }}
.signature-block .sig-date {{ font-size: 11px; color: #999; }}

/* ── 页脚 ── */
.footer {{
  margin-top: 30px; padding-top: 8px; border-top: 1px solid #d4d4d4;
  font-size: 10px; color: #999; text-align: center;
}}

/* ── 打印样式 ── */
@media print {{
  body {{ font-size: 11px; }}
  .no-print {{ display: none !important; }}
  .header {{ border-bottom-color: #000; }}
  .assessment-box {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .score-bar-pass, .score-bar-fail {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .badge-danger, .badge-warn {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .cat-header td {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  table.findings th {{ background: #1a1a1a !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .page-break {{ page-break-before: always; }}
}}
</style>
</head>
<body>

<!-- ═══ 页头 ═══ -->
<div class="header">
  <div class="header-left">
    <h1>消防监督检查记录表</h1>
    <div class="dept">上饶市消防救援支队</div>
  </div>
  <div class="header-right">
    <div class="report-no">编号：{inspection_id}</div>
    <div class="qr-box">
      <img src="https://api.qrserver.com/v1/create-qr-code/?size=80x80&data={qr_url}" alt="扫码查看报告" width="64" height="64">
      <div class="qr-label">扫码在线查看</div>
    </div>
  </div>
</div>

<!-- ═══ 基本信息 ═══ -->
<div class="info-grid">
  <div class="info-item"><div class="info-label">场所名称</div><div class="info-value">{insp.get('venue_name', '')}</div></div>
  <div class="info-item"><div class="info-label">场所类型</div><div class="info-value">{insp.get('venue_type', '')}</div></div>
  <div class="info-item"><div class="info-label">检查地址</div><div class="info-value">{insp.get('location', '')}</div></div>
  <div class="info-item"><div class="info-label">检查日期</div><div class="info-value">{insp.get('started_at', '')[:10]}</div></div>
  <div class="info-item"><div class="info-label">检查人员</div><div class="info-value">{insp.get('inspector', '')}</div></div>
  <div class="info-item"><div class="info-label">检查模式</div><div class="info-value">{'🔁 复查' if insp.get('mode')=='recheck' else '🆕 首次检查'}</div></div>
</div>

<!-- ═══ 评分概要 ═══ -->
<div class="score-section">
  <div class="score-cards">
    <div class="score-card pass">
      <div class="num">{len(passes)}</div>
      <div class="label">✅ 合格项</div>
    </div>
    <div class="score-card fail">
      <div class="num">{len(fails)}</div>
      <div class="label">❌ 不合格项</div>
    </div>
    <div class="score-card na-card">
      <div class="num">{len(na_items)}</div>
      <div class="label">⊘ 不涉及</div>
    </div>
    <div class="score-card">
      <div class="num">{total}</div>
      <div class="label">📋 总检查项</div>
    </div>
  </div>

  <div class="score-bar-wrap">
    <div class="score-bar-pass" style="width:{pass_pct}%">{pass_pct}%</div>
    <div class="score-bar-fail" style="width:{fail_pct}%">{fail_pct}%</div>
    <div class="score-bar-na" style="width:{100-pass_pct-fail_pct}%"></div>
  </div>

  <div class="assessment-box">
    综合评估：{assessment.get('score', 0)} 分 — {color_label.get(assessment.get('color', 'green'), '')}
    {f'（复查期限：{assessment.get("next_recheck_days", 90)} 日内）' if assessment.get('next_recheck_days') else ''}
  </div>
</div>

<!-- ═══ 检查明细 ═══ -->
<h3 style="font-size:15px;margin:20px 0 8px;color:#1a1a1a;">检查明细</h3>
<table class="findings">
<thead>
<tr>
  <th>序号</th><th>检查部位</th><th>检查要点</th><th>等级</th><th>判定</th><th>备注</th>
</tr>
</thead>
<tbody>
{items_html}
</tbody>
</table>

<!-- ═══ 签名 ═══ -->
<div class="signature-area">
  <div class="signature-block">
    <div class="signature-line"></div>
    <div class="sig-label">检查人员签字</div>
    <div class="sig-date">{datetime.now().strftime('%Y 年 %m 月 %d 日')}</div>
  </div>
  <div class="signature-block">
    <div class="signature-line"></div>
    <div class="sig-label">被检查单位负责人签字</div>
    <div class="sig-date">　</div>
  </div>
</div>

<div class="footer">
  <p>本报告由消防监督检查智能辅助系统生成 · 报告编号 {inspection_id}</p>
  <p>上饶市消防救援支队 · 生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</div>

  <div class="signature-area">
    <div class="signature-item">
      <div class="label">检查人（签字）</div>
      <div class="date">{insp.get("inspector", "") or "　　　　　　"}</div>
    </div>
    <div class="signature-item">
      <div class="label">被检查单位负责人（签字）</div>
      <div class="date"></div>
    </div>
    <div class="signature-item">
      <div class="label">日期</div>
      <div class="date">{(insp.get("completed_at") or insp.get("started_at") or "")[:10]}</div>
    </div>
  </div>
  <div class="page-footer">
    <span>编号：{inspection_id}</span>
    <span>本记录一式两份，检查单位和被检查单位各执一份</span>
    <span>生成时间：<span class="no-print">{gen_time}</span></span>
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
    writer.writerow(["序号", "类别", "检查部位", "检查要点", "严重程度", "是否强制项", "判定", "备注"])

    for i, f in enumerate(findings):
        writer.writerow([
            i + 1,
            f.get("category", ""),
            f.get("facility", ""),
            f.get("check_point", ""),
            f.get("severity", ""),
            "是" if f.get("is_mandatory") else "",
            f.get("result", ""),
            f.get("note", ""),
        ])

    return ("﻿" + output.getvalue()).encode("utf-8")
