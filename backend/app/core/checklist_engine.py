"""
检查流程引擎 — Fire-Inspect 核心模块
负责: 场景匹配、逐项引导、抽查比例计算、复查逻辑

这是 checklist_engine 的 canonical 实现。
根目录 checklist_engine.py 是兼容性重导出 shim。
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Optional

from .config import settings

# ── 法规来源中文全称映射 ──────────────────────────────────────
SOURCE_FULL_NAMES = {
    # 国家法律
    "中华人民共和国消防法(2021修订)": "《中华人民共和国消防法》(2021年修订)",
    "中华人民共和国消防法": "《中华人民共和国消防法》",
    "《中华人民共和国消防法》(2021修正)": "《中华人民共和国消防法》(2021年修正)",
    "中华人民共和国安全生产法": "《中华人民共和国安全生产法》",
    # 部令/部门规章
    "机关团体企业事业单位消防安全管理规定(公安部61号令)": "《机关、团体、企业、事业单位消防安全管理规定》(公安部令第61号)",
    "《机关、团体、企业、事业单位消防安全管理规定》公安部令第61号": "《机关、团体、企业、事业单位消防安全管理规定》(公安部令第61号)",
    "消防监督检查规定(公安部令第120号)": "《消防监督检查规定》(公安部令第120号)",
    "《消防监督检查规定》公安部令第120号": "《消防监督检查规定》(公安部令第120号)",
    "消防产品监督管理规定": "《消防产品监督管理规定》",
    "《消防产品监督管理规定》": "《消防产品监督管理规定》",
    # 国家标准
    "GB 46034-2025": "《人员密集场所投入使用营业消防安全检查规范》GB 46034-2025",
    "GB 50016-2014": "《建筑设计防火规范》GB 50016-2014",
    "GB 50016-2014(2018)": "《建筑设计防火规范》GB 50016-2014(2018年版)",
    "GB 50116-2013": "《火灾自动报警系统设计规范》GB 50116-2013",
    "GB 50140-2005": "《建筑灭火器配置设计规范》GB 50140-2005",
    "GB 50151-2021": "《泡沫灭火系统技术标准》GB 50151-2021",
    "GB 25201": "《建筑消防设施维护管理规范》GB 25201",
    "GB 25506-2010": "《消防控制室通用技术要求》GB 25506-2010",
    "GB 50028-2006": "《城镇燃气设计规范》GB 50028-2006",
    "GB 50370-2005": "《气体灭火系统设计规范》GB 50370-2005",
    "GB 50974-2014": "《消防给水及消火栓系统技术规范》GB 50974-2014",
    "GB 55037-2022": "《建筑防火通用规范》GB 55037-2022",
    "GB 35181-2025": "《重大火灾隐患判定方法》GB 35181-2025",
    "《建筑消防设施的维护管理》GB 25201": "《建筑消防设施的维护管理》GB 25201",
    "GA 654-2006": "《人员密集场所消防安全管理》GA 654-2006",
    "GB/T 40248-2021": "《人员密集场所消防安全管理》GB/T 40248-2021",
    "GB/T 38315-2019": "《社会单位灭火和应急疏散预案编制及实施导则》GB/T 38315-2019",
    "GB 46034-2025 / GB 25506-2010": "GB 46034-2025 / GB 25506-2010",
    # 地方标准
    "DB36/T 922-2023": "《娱乐场所消防安全管理规范》DB36/T 922-2023",
    "DB36/T 923-2023": "《商场市场消防安全管理规范》DB36/T 923-2023",
    "《公共娱乐场所消防安全管理规范》DB36/T 922-2023": "《公共娱乐场所消防安全管理规范》DB36/T 922-2023",
    "《商场市场消防安全管理规范》DB36/T 923-2023": "《商场市场消防安全管理规范》DB36/T 923-2023",
    # 省级法规
    "江西省消防条例(2020年修正版)": "《江西省消防条例》(2020年修正版)",
    "《江西省消防条例》(2020年第六次修正)": "《江西省消防条例》(2020年第六次修正)",
    "江西省消防安全责任制实施办法(省政府令252号)": "《江西省消防安全责任制实施办法》(省政府令第252号)",
    "《江西省消防安全责任制实施办法》省政府令第252号": "《江西省消防安全责任制实施办法》(省政府令第252号)",
    "赣消办2025年13号": '赣消办〔2025〕13号《关于建立"9+N"小场所消防安全监管长效机制的实施意见》',
    "赣府厅发〔2025〕13号《关于建立\"9+N\"小场所消防安全监管长效机制的实施意见》": '赣府厅发〔2025〕13号《关于建立"9+N"小场所消防安全监管长效机制的实施意见》',
    "《江西省消防安全重点单位界定标准》(2024年)": "《江西省消防安全重点单位界定标准》(2024年)",
}

# ── 法规层级优先级（越小越靠前）─────────────────────────────
SOURCE_TYPE_PRIORITY = {
    "national_standard": 0,
    "province_standard": 1,
    "department_rule": 10,
    "ministry_order": 20,
    "province_regulation": 25,
    "national_law": 30,
    "law": 31,
}


# ── source_type 中英归一化 ─────────────────────────────────
def _normalize_source_type(st: str) -> str:
    """将中文 source_type 归一化为英文 key，未匹配返回原值"""
    _map = {
        "国标": "national_standard", "国家标准": "national_standard",
        "地标": "province_standard", "地方标准": "province_standard",
        "法律": "law", "国家法律": "national_law",
        "部令": "ministry_order", "部门规章": "department_rule",
        "省条例": "province_regulation", "省级法规": "province_regulation",
        "规定": "department_rule", "办法": "department_rule",
        "行业标准": "national_standard",
    }
    return _map.get(st, st)


def _parse_article_num(source_text: str) -> float:
    """从法规来源字符串中提取条号用于排序，如 第5.1条 → 5.1"""
    if not source_text:
        return 9999.0
    m = re.search(r"第\s*(\d+(?:\.\d+)?)\s*条", source_text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)$", source_text)
    if m:
        return float(m.group(1))
    return 9999.0


class ChecklistEngine:
    """检查流程引擎"""

    def __init__(self) -> None:
        self._checklist_config: Optional[Dict] = None
        self._rules: Optional[List[Dict]] = None

    # ------------------------------------------------------------------
    # 加载配置
    # ------------------------------------------------------------------
    @property
    def checklist_config(self) -> Dict:
        if self._checklist_config is None:
            # 优先根目录（最新），fallback app/data/
            for cfg_path in [
                settings.BASE_DIR / "checklist_config.json",
                settings.BASE_DIR / "app" / "data" / "checklist_config.json",
            ]:
                if cfg_path.exists():
                    self._checklist_config = json.loads(cfg_path.read_text("utf-8"))
                    break
            else:
                self._checklist_config = self._default_config()
        return self._checklist_config

    @property
    def rules(self) -> List[Dict]:
        if self._rules is None:
            rules_path = settings.RULES_FILE
            if rules_path.exists():
                kb = json.loads(rules_path.read_text("utf-8"))
                self._rules = kb.get("rules", [])
            else:
                self._rules = []
        return self._rules

    @staticmethod
    def _default_config() -> Dict:
        return {
            "scenes": {},
            "sampling_rules": {
                "staff": {"rules": [{"min": 0, "max": 5, "sample": "all"}]},
                "floors": {"rules": [{"min": 1, "max": 3, "sample": "all"}]},
            },
        }

    # ------------------------------------------------------------------
    # 场景信息
    # ------------------------------------------------------------------
    def get_scene_info(self, venue_type: str) -> Dict:
        scenes = self.checklist_config.get("scenes", {})
        return scenes.get(venue_type, {"name": venue_type, "total_items": 25})

    def list_scenes(self) -> List[Dict]:
        scenes = self.checklist_config.get("scenes", {})
        return [
            {"key": k, "name": v.get("name", k), "total_items": v.get("total_items", 0)}
            for k, v in scenes.items()
        ]

    # ------------------------------------------------------------------
    # 抽查比例计算
    # ------------------------------------------------------------------
    def calc_staff_sample(self, staff_count: int) -> Dict:
        rules = self.checklist_config.get("sampling_rules", {}).get("staff", {}).get("rules", [])
        for r in rules:
            if r["min"] <= staff_count <= r["max"]:
                sample = staff_count if r["sample"] == "all" else r["sample"]
                return {"sample": sample, "total": staff_count, "label": r.get("label", "")}
        return {"sample": min(staff_count, 5), "total": staff_count, "label": "默认至少5人"}

    def calc_floor_sample(self, floor_count: int) -> Dict:
        rules = self.checklist_config.get("sampling_rules", {}).get("floors", {}).get("rules", [])
        for r in rules:
            if r["min"] <= floor_count <= r["max"]:
                if r.get("sample") == "all":
                    sample = floor_count
                elif "sample_fraction" in r:
                    sample = max(1, math.ceil(floor_count * r["sample_fraction"]))
                else:
                    sample = r.get("sample", floor_count)
                return {"sample": sample, "total": floor_count, "label": r.get("label", "")}
        return {"sample": min(floor_count, 3), "total": floor_count, "label": "默认至少3层"}

    # ── 九小场所精简规则 ─────────────────────────
    _NINE_SMALL_KEEP = {
        "DAILY-3.1-1", "DAILY-3.1-2", "DAILY-3.1-3", "DAILY-LEGAL-1",
        "DAILY-3.2-1", "DAILY-3.2-2", "DAILY-3.2-4", "DAILY-3.2-5", "DAILY-3.2-6",
        "DAILY-3.3-EXT-1", "DAILY-3.3-EXT-2",
        "DAILY-3.3-HYDR-1", "DAILY-3.3-HYDR-2",
        "DAILY-3.3-ALARM-1", "DAILY-3.3-ALARM-2",
        "DAILY-3.3-EVAC-1", "DAILY-3.3-EVAC-2",
        "DAILY-3.6-1",
        "DAILY-3.4-1", "DAILY-3.4-2",
        "DAILY-3.7-1",
    }

    _DAILY_STEP_FALLBACK: list[tuple[set[str], int]] = [
        ({"消防控制室","控制室值班","控制室设置","控制室管理",
          "消防电话","消防应急广播","控制室反馈","消防通信"}, 5),
        ({"火灾自动报警","探测器","手动报警","声光","消火栓","消防给水",
          "消防水泵","水泵房","消防水池","消防水箱","稳压泵","水泵接合器",
          "启泵","供水","消防水源","系统接地"}, 6),
        ({"自动喷水","喷水","喷头","报警阀","水流指示器","末端试水",
          "气体灭火","储瓶","防护区","泡沫","灭火器",
          "排烟","送风","防排烟","挡烟垂壁","排烟口","排烟风机",
          "消防电梯","消防供电","发电机","备用电源","储油",
          "防火门","防火卷帘","闭门器","顺序器","防火阀",
          "合格证","CCC","消防产品","产品认证","型式检验",
          "洒水","湿式"}, 7),
        ({"防火分区","防火间距","消防车道","消防车通道",
          "装修材料","内部装修","外墙保温","保温材料",
          "电缆井","管道井","封堵","防火墙","防火分隔",
          "平面布置","总平面","场所设置","防火窗","登高","救援窗",
          "防烟分区"}, 3),
        ({"疏散","安全出口","疏散走道","疏散楼梯","避难层",
          "安全疏散","应急照明","疏散指示","应急灯","疏散标志"}, 4),
        ({"隐患整改","重大火灾隐患","既往隐患","燃气","燃气管道",
          "厨房","烟道","用火用电","动火","吸烟","微型消防站",
          "档案","重点部位"}, 8),
        ({"消防设计","消防验收","开业前","使用性质","合法性"}, 1),
        ({"责任制","责任人","管理人","制度","预案","巡查","培训","演练",
          "值班","持证","维保","标识","消防组织","消防职责"}, 2),
    ]

    @classmethod
    def _assign_daily_step(cls, rule: Dict) -> int:
        new_step = rule.get("daily_step_new")
        if new_step:
            return new_step
        old_step = rule.get("daily_step") or 0
        _old_to_new = {31: 1, 32: 2, 35: 7, 36: 8, 37: 8}
        if old_step in _old_to_new:
            return _old_to_new[old_step]
        facility = rule.get("title", "") + rule.get("facility", "") + rule.get("check_point", "")
        category = rule.get("category", "")
        combined = facility + category
        for keywords, step in cls._DAILY_STEP_FALLBACK:
            for kw in keywords:
                if kw in combined:
                    return step
        return 7 if category == "设施完好" else 2 if category == "消防管理" else 7

    # ------------------------------------------------------------------
    # 检查项生成
    # ------------------------------------------------------------------
    def get_check_items(self, venue_type: str, inspection_type: str = "preopen") -> List[Dict]:
        self.get_scene_info(venue_type)

        items = []
        for rule in self.rules:
            itype = rule.get("inspection_type", "both")
            if itype == "reference_only":
                continue
            if inspection_type == "preopen" and itype == "daily":
                continue
            if inspection_type == "daily" and itype == "preopen":
                continue
            scenes = rule.get("scene", [])
            if venue_type not in scenes:
                continue
            if venue_type == "nine_small" and inspection_type == "daily":
                rid = rule.get("id", "")
                if rid not in self._NINE_SMALL_KEEP:
                    continue

            item = {
                "rule_id": rule["id"],
                "title": rule.get("title", ""),
                "facility": self._extract_facility(rule),
                "check_point": rule.get("check_point", rule.get("title", "")),
                "check_method": rule.get("check_method", "现场检查"),
                "category": rule.get("category", "技术条件"),
                "severity": rule.get("severity", "normal"),
                "is_mandatory": rule.get("is_mandatory", False),
                "preopen_order": rule.get("preopen_order") or 0,
                "daily_order": rule.get("daily_order") or 0,
                "preopen_section": rule.get("preopen_section", 0),
                "preopen_group": rule.get("preopen_group", 0),
                "preopen_sub": rule.get("preopen_sub", 0),
                "regulation": {
                    "source": self._format_source(rule),
                    "text": rule.get("text") or rule.get("check_point", ""),
                    "source_type": _normalize_source_type(rule.get("source_type", "")),
                    "province": rule.get("province"),
                },
                "province_regulations": self._find_related_province_rules(rule),
                "step": self._assign_daily_step(rule) if inspection_type == "daily" else rule.get("step", 5),
                "step_name": rule.get("daily_step_name", rule.get("step_name", "")) if inspection_type == "daily" else rule.get("step_name", ""),
                "qa_config": rule.get("qa_config"),
            }
            items.append(item)

        if inspection_type == "daily":
            items.sort(key=lambda x: (
                x.get("step", 5),
                SOURCE_TYPE_PRIORITY.get(_normalize_source_type(x["regulation"]["source_type"]), 50),
                x.get("daily_order") or 9999,
                0 if x["is_mandatory"] else 1,
            ))
        else:
            items.sort(key=lambda x: (
                x.get("preopen_section") or 9,
                x.get("preopen_group") or 9,
                x.get("preopen_sub") or 99,
                x.get("preopen_order") or 9999,
                SOURCE_TYPE_PRIORITY.get(_normalize_source_type(x["regulation"]["source_type"]), 50),
                _parse_article_num(x["regulation"].get("source", "")),
                0 if x["is_mandatory"] else 1,
            ))

        return items

    @staticmethod
    def _format_source(rule: Dict) -> str:
        src = rule.get('source', '')
        full_name = SOURCE_FULL_NAMES.get(src, src)
        art = rule.get('article', '')
        if not art:
            return full_name
        if '第' in art and '条' in art:
            return f"{full_name} {art}"
        return f"{full_name} 第{art}条"

    def _extract_facility(self, rule: Dict) -> str:
        title = rule.get("title", "")
        facility_map = {
            "责任制": "消防安全责任制", "责任人": "消防安全责任人",
            "消防控制室": "消防控制室", "动火": "动火作业管理",
            "维护保养": "消防设施维护", "防火巡查": "防火巡查检查",
            "隐患整改": "火灾隐患整改", "易燃易爆": "易燃易爆品管理",
            "预案": "应急预案与演练", "消防档案": "消防档案",
            "总平面": "总平面布局", "外墙": "建筑外墙保温",
            "装修": "内部装修材料", "防火分区": "防火分区",
            "安全疏散": "安全疏散设施", "疏散指示": "疏散指示标志",
            "消防电梯": "消防电梯", "消火栓": "消火栓系统",
            "火灾自动报警": "火灾自动报警系统", "自动喷水": "自动喷水灭火系统",
            "防排烟": "防排烟系统", "消防供电": "消防供电",
            "灭火器": "灭火器配置", "电气": "电气线路安全",
            "防火门": "防火门/防火卷帘", "未经许可": "开业前许可",
            "发电机": "发电机房", "储油": "储油间",
            "消防电话": "消防电话系统", "应急广播": "消防应急广播系统",
            "气体灭火": "气体灭火系统", "泡沫": "泡沫灭火系统",
            "防火卷帘": "防火卷帘", "启泵": "消火栓启泵按钮",
            "喷头": "自动喷水喷头", "报警阀": "报警阀组",
            "末端试水": "末端试水装置", "控制器": "火灾报警控制器",
            "探测器": "火灾探测器", "控制室反馈": "消防控制室信号反馈",
            "声光": "火灾声光报警器", "手动报警": "手动火灾报警按钮",
            "接地": "系统接地", "洒水": "洒水喷头",
            "湿式": "湿式报警阀组", "水流指示器": "水流指示器",
            "水泵接合器": "消防水泵接合器", "自然排烟": "自然排烟窗",
            "防烟分区": "防烟分区", "顺序器": "防火门顺序器",
            "闭门器": "防火门闭门器", "耐火": "防火门耐火等级",
            "排烟管道": "发电机排烟管道", "自启动": "发电机自启动",
            "分机": "消防电话分机", "扬声器": "应急广播扬声器",
            "分区广播": "应急广播分区", "备用电源": "应急广播备用电源",
            "强制切换": "应急广播强制切换", "储瓶": "气体灭火储瓶",
            "防护区": "气体灭火防护区", "泡沫液": "泡沫液储罐",
            "比例混合": "泡沫比例混合器", "泡沫产生": "泡沫产生器",
        }
        for key, facility in facility_map.items():
            if key in title:
                return facility
        return title[:30]

    def _find_related_province_rules(self, rule: Dict) -> List[Dict]:
        related_ids = rule.get("related_rules", [])
        province_rules = []
        for rid in related_ids:
            for r in self.rules:
                if r["id"] == rid and r.get("province") and r.get("source_type") in ("province_regulation", "province_standard"):
                    province_rules.append({
                        "id": r["id"], "source": r["source"],
                        "article": r.get("article", ""),
                        "text": r.get("text", "")[:200],
                    })
        return province_rules

    # ------------------------------------------------------------------
    # 复查逻辑
    # ------------------------------------------------------------------
    def sort_items_for_recheck(
        self, items: List[Dict], previous_fail_ids: List[str]
    ) -> List[Dict]:
        failed_items = [i for i in items if i["rule_id"] in previous_fail_ids]
        other_items = [i for i in items if i["rule_id"] not in previous_fail_ids]
        for item in failed_items:
            item["is_recheck_item"] = True
        for item in other_items:
            item["is_recheck_item"] = False
        return failed_items + other_items

    # ------------------------------------------------------------------
    # 四色评分
    # ------------------------------------------------------------------
    def calculate_assessment(self, findings: List[Dict]) -> Dict[str, Any]:
        score = 100
        mandatory_count = 0
        important_count = 0
        normal_count = 0
        deductions = []
        category_scores = {"消防管理": 100, "技术条件": 100, "设施完好": 100}

        for f in findings:
            if f.get("result") != "fail":
                continue
            severity = f.get("severity", "normal")
            is_mandatory = f.get("is_mandatory", False)
            category = f.get("category", "技术条件")

            if is_mandatory or severity == "important":
                penalty = 30 if is_mandatory else 15
                if is_mandatory:
                    mandatory_count += 1
                else:
                    important_count += 1
            else:
                penalty = 5
                normal_count += 1

            score -= penalty
            category_scores[category] = max(0, category_scores.get(category, 100) - penalty)
            deductions.append({
                "rule_id": f.get("rule_id", ""),
                "facility": f.get("facility", ""),
                "points": -penalty,
                "detail": f.get("note", f.get("check_point", "")),
            })

        score = max(0, score)

        if score <= 40:
            color, color_label, risk_level = "red", "高风险", 4
            deadline_days, measures = 15, ["挂牌督办", "通报属地政府", "约谈负责人", "临时查封(符合条件时)"]
        elif score <= 60:
            color, color_label, risk_level = "orange", "较高风险", 3
            deadline_days, measures = 30, ["重点监管", "增加检查频次", "限期整改跟踪"]
        elif score <= 80:
            color, color_label, risk_level = "yellow", "一般风险", 2
            deadline_days, measures = 60, ["常规监管", "业主自行整改", "抽查验证"]
        else:
            color, color_label, risk_level = "green", "低风险", 1
            deadline_days, measures = 180, ["正常管理", "鼓励保持"]

        return {
            "score": score,
            "color": color,
            "color_label": color_label,
            "risk_level": risk_level,
            "summary": {
                "mandatory_violations": mandatory_count,
                "important_hazards": important_count,
                "normal_hazards": normal_count,
            },
            "deductions": deductions,
            "radar": category_scores,
            "next_recheck_days": deadline_days,
            "supervision_measures": measures,
        }


# 全局单例
checklist_engine = ChecklistEngine()
