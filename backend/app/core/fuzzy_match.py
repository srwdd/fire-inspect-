"""
消防语音模糊匹配引擎
─────────────────────────────────────────
解决普通话不标准（南方口音）导致的语音识别匹配失败问题。

三层防护:
  1. 拼音转换 → 统一映射到拼音空间
  2. 混淆模式展开 → 针对 zh/z, sh/s, ch/c, n/l, -n/-ng 等常见口音
  3. 编辑距离匹配 → 允许少量字符差异

使用:
  from app.core.fuzzy_match import FuzzyMatcher
  fm = FuzzyMatcher()
  result = fm.classify_judgment("合格")  # → {result: "pass", confidence: 0.95}
  matches = fm.search_items("mie huo qi", all_items)  # → 排名列表
"""

from __future__ import annotations

import re
from typing import Optional

try:
    from pypinyin import lazy_pinyin, Style
    HAS_PINYIN = True
except ImportError:
    HAS_PINYIN = False


# ═══════════════════════════════════════════════════
# 南方口音常见混淆 → 归一化到标准拼音
# ═══════════════════════════════════════════════════

# 1. 翘舌→平舌 (zh→z, ch→c, sh→s)
RETROFLEX_TO_FLAT = {
    'zha': 'za',  'zhai': 'zai', 'zhan': 'zan', 'zhang': 'zang',
    'zhao': 'zao', 'zhe': 'ze',  'zhen': 'zen', 'zheng': 'zeng',
    'zhi': 'zi',  'zhong': 'zong','zhou': 'zou', 'zhu': 'zu',
    'zhua': 'zua', 'zhuai': 'zuai','zhuan': 'zuan','zhuang': 'zuang',
    'zhui': 'zui', 'zhun': 'zun', 'zhuo': 'zuo',
    'cha': 'ca',  'chai': 'cai', 'chan': 'can', 'chang': 'cang',
    'chao': 'cao', 'che': 'ce',  'chen': 'cen', 'cheng': 'ceng',
    'chi': 'ci',  'chong': 'cong','chou': 'cou', 'chu': 'cu',
    'chuai': 'cuai','chuan': 'cuan','chuang': 'cuang',
    'chui': 'cui', 'chun': 'cun', 'chuo': 'cuo',
    'sha': 'sa',  'shai': 'sai', 'shan': 'san', 'shang': 'sang',
    'shao': 'sao', 'she': 'se',  'shen': 'sen', 'sheng': 'seng',
    'shi': 'si',  'shou': 'sou', 'shu': 'su',  'shua': 'sua',
    'shuai': 'suai','shuan': 'suan','shuang': 'suang',
    'shui': 'sui', 'shun': 'sun', 'shuo': 'suo',
}

# 2. n/l 混淆
def _nl_variants(py: str) -> set:
    """生成 n↔l 混淆变体"""
    if py.startswith('n') and not py.startswith('ng'):
        return {py, 'l' + py[1:]}
    if py.startswith('l'):
        return {py, 'n' + py[1:]}
    return {py}

# 3. 前后鼻音混淆 (-n ↔ -ng)
def _nasal_variants(py: str) -> set:
    """生成 -n ↔ -ng 混淆变体"""
    variants = {py}
    if py.endswith('ng'):
        variants.add(py[:-2] + 'n')
    elif py.endswith('n') and not py.endswith('en') and not py.endswith('in'):
        # 保守：只对明显的鼻音韵尾做变换
        if len(py) >= 3 and py[-3:] not in ('ien', 'uen'):
            variants.add(py[:-1] + 'ng')
    return variants

# 4. r/l 混淆 (南方部分地区)
def _rl_variants(py: str) -> set:
    """生成 r↔l 混淆变体"""
    if py.startswith('r'):
        return {py, 'l' + py[1:]}
    if py.startswith('l'):
        return {py, 'r' + py[1:]}
    return {py}

# 5. h/f 混淆（闽南/客家等）
def _hf_variants(py: str) -> set:
    """生成 h↔f 混淆变体（闽南/客家话影响）"""
    if py.startswith('hu'):
        return {py, 'f' + py[2:]}
    if py.startswith('f') and not py.startswith('fa') and not py.startswith('fo'):
        return {py, 'hu' + py[1:]}
    return {py}


def normalize_pinyin(py: str) -> str:
    """将拼音标准化：去声调、去翘舌→平舌、统一格式"""
    # 去掉声调数字
    py = re.sub(r'[1-5]$', '', py.strip().lower())
    # 翘舌→平舌
    if py in RETROFLEX_TO_FLAT:
        py = RETROFLEX_TO_FLAT[py]
    return py


def expand_variants(pinyin_list: list[str]) -> set[str]:
    """对拼音序列展开所有口音变体"""
    variants = {''}
    for py in pinyin_list:
        py = normalize_pinyin(py)
        new_variants = set()
        all_forms = {py}
        all_forms.update(_nl_variants(py))
        all_forms.update(_nasal_variants(py))
        all_forms.update(_rl_variants(py))
        all_forms.update(_hf_variants(py))
        for form in all_forms:
            for base in variants:
                new_variants.add(base + ' ' + form if base else form)
        variants = new_variants
    return variants


def pinyin_similarity(a: str, b: str) -> float:
    """
    计算两个拼音序列的相似度 (0~1)
    使用词级别Jaccard + 编辑距离混合
    """
    a_words = a.strip().split()
    b_words = b.strip().split()
    if not a_words or not b_words:
        return 0.0

    # 词级别 Jaccard（处理顺序变化）
    intersection = len(set(a_words) & set(b_words))
    union = len(set(a_words) | set(b_words))
    jaccard = intersection / union if union > 0 else 0

    # 序列编辑距离（处理整体相似度）
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    edit_dist = _levenshtein(a, b)
    edit_sim = 1.0 - edit_dist / max_len

    return 0.4 * jaccard + 0.6 * edit_sim


def _levenshtein(s1: str, s2: str) -> int:
    """Levenshtein编辑距离"""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(
                prev[j + 1] + 1,     # 插入
                curr[j] + 1,          # 删除
                prev[j] + (0 if c1 == c2 else 1)  # 替换
            ))
        prev = curr
    return prev[-1]


# ═══════════════════════════════════════════════════
# 消防专业词汇 → 拼音映射（内置高频词，脱网可用）
# ═══════════════════════════════════════════════════

FIRE_VOCABULARY: dict[str, str] = {
    # 判定词
    "合格": "he ge",
    "正常": "zheng chang",
    "没问题": "mei wen ti",
    "通过": "tong guo",
    "符合": "fu he",
    "合格项": "he ge xiang",
    "没问题啊": "mei wen ti a",

    "不合格": "bu he ge",
    "有问题": "you wen ti",
    "不行": "bu xing",
    "隐患": "yin huan",
    "过期": "guo qi",
    "损坏": "sun huai",
    "缺失": "que shi",
    "堵塞": "du se",
    "故障": "gu zhang",
    "失效": "shi xiao",
    "坏了": "huai le",
    "不行了": "bu xing le",
    "不能用": "bu neng yong",
    "不符合": "bu fu he",

    "不涉及": "bu she ji",
    "不适用": "bu shi yong",
    "没有这个": "mei you zhe ge",
    "没有": "mei you",
    "跳过": "tiao guo",
    "不用检": "bu yong jian",

    # 消防设施
    "灭火器": "mie huo qi",
    "消火栓": "xiao huo shuan",
    "消防栓": "xiao fang shuan",
    "自动喷淋": "zi dong pen lin",
    "喷淋": "pen lin",
    "烟感": "yan gan",
    "温感": "wen gan",
    "火灾报警": "huo zai bao jing",
    "报警器": "bao jing qi",
    "消防控制室": "xiao fang kong zhi shi",
    "疏散通道": "shu san tong dao",
    "安全出口": "an quan chu kou",
    "防火门": "fang huo men",
    "防火卷帘": "fang huo juan lian",
    "应急照明": "ying ji zhao ming",
    "疏散指示": "shu san zhi shi",
    "排烟": "pai yan",
    "防排烟": "fang pai yan",
    "消防电梯": "xiao fang dian ti",
    "水泵": "shui beng",
    "消防水泵": "xiao fang shui beng",
    "消防水池": "xiao fang shui chi",
    "消防电源": "xiao fang dian yuan",
    "发电机": "fa dian ji",
    "配电房": "pei dian fang",
    "燃气": "ran qi",
    "电气线路": "dian qi xian lu",
    "消防车道": "xiao fang che dao",
    "登高面": "deng gao mian",
    "消防": "xiao fang",

    # 拍照/操作
    "拍照": "pai zhao",
    "拍个照": "pai ge zhao",
    "照相": "zhao xiang",
    "拍一张": "pai yi zhang",

    # 场景场所
    "宾馆": "bin guan",
    "酒店": "jiu dian",
    "商场": "shang chang",
    "市场": "shi chang",
    "学校": "xue xiao",
    "幼儿园": "you er yuan",
    "医院": "yi yuan",
    "养老院": "yang lao yuan",
    "养老机构": "yang lao ji gou",
    "娱乐场所": "yu le chang suo",
    "网吧": "wang ba",
    "KTV": "ktv",
    "仓库": "cang ku",
    "厂房": "chang fang",
    "办公楼": "ban gong lou",
    "高层": "gao ceng",
    "地下": "di xia",
    "地下室": "di xia shi",
}

# ═══════════════════════════════════════════════════
# 判定分类器
# ═══════════════════════════════════════════════════

# 标准判断词（已展开到拼音空间）
_PASS_KEYWORDS = {
    "he ge", "zheng chang", "mei wen ti", "tong guo", "fu he",
    "hao de", "dui de", "ke yi", "mei shi", "zheng que",
}
_FAIL_KEYWORDS = {
    "bu he ge", "you wen ti", "bu xing", "yin huan", "guo qi",
    "sun huai", "que shi", "du se", "gu zhang", "shi xiao",
    "huai le", "bu neng yong", "bu fu he", "bu hao", "cuo le",
    "you que xian", "xu yao xiu", "xu yao huan",
}
_SKIP_KEYWORDS = {
    "bu she ji", "bu shi yong", "mei you zhe ge", "mei you",
    "tiao guo", "bu yong jian", "wuyong", "na", "naa",
    "bu xu yao", "bu jian",
}
_PHOTO_KEYWORDS = {
    "pai zhao", "pai ge zhao", "zhao xiang", "pai yi zhang",
    "pai pian", "pai xia lai", "she xiang",
}


class FuzzyMatcher:
    """消防语音模糊匹配器"""

    def __init__(self):
        self._fire_vocab_pinyin: dict[str, str] = {}
        if HAS_PINYIN:
            # 动态获取任何中文文本的拼音，同时预计算内置词汇
            self._fire_vocab_pinyin = FIRE_VOCABULARY.copy()

    def to_pinyin(self, text: str) -> str:
        """将中文文本转为拼音序列（空格分隔）"""
        if not text or not text.strip():
            return ""
        if HAS_PINYIN:
            pinyin_list = lazy_pinyin(text.strip(), style=Style.TONE3)
            normalized = [normalize_pinyin(p) for p in pinyin_list]
            return ' '.join(normalized)
        else:
            # 回退：逐词查内置表
            result = []
            for ch in text.strip():
                result.append(self._fire_vocab_pinyin.get(ch, ch.lower()))
            return ' '.join(result)

    def classify_judgment(self, text: str) -> dict:
        """
        将语音转录文本分类为判定动作。

        返回:
          {
            "action": "pass" | "fail" | "skip" | "photo" | "unknown",
            "confidence": 0.0 ~ 1.0,
            "note": "原始文本或解释",
            "matched_keyword": "匹配到的关键词"
          }
        """
        text = text.strip()
        if not text:
            return {"action": "unknown", "confidence": 0, "note": text, "matched_keyword": ""}

        text_pinyin = self.to_pinyin(text)

        # 1. 先尝试精确中文匹配（最高置信度，保留原逻辑兼容）
        has_positive = bool(re.search(r'合格|没问题|正常|符合|通过|合规', text))
        has_negative = bool(re.search(r'不', text))

        if has_positive and not has_negative:
            return {"action": "pass", "confidence": 1.0, "note": text, "matched_keyword": "exact_zh:pass"}

        neg_keywords = r'不合格|有问题|不行|隐患|过期|损坏|缺失|堵塞|故障|失效|坏了|不能用|不符合'
        if re.search(neg_keywords, text):
            note = re.sub(r'不合格[，。,.\s]*', '', text)
            note = re.sub(r'有问题[，。,.\s]*', '', note)
            if not note.strip():
                note = text
            return {"action": "fail", "confidence": 1.0, "note": note, "matched_keyword": "exact_zh:fail"}

        if re.search(r'跳过|不涉及|N/?A|不适用|没有这个|不用检', text):
            return {"action": "skip", "confidence": 1.0, "note": "不涉及", "matched_keyword": "exact_zh:skip"}

        if re.search(r'拍照|拍个照|照相|拍一张', text):
            return {"action": "photo", "confidence": 1.0, "note": text, "matched_keyword": "exact_zh:photo"}

        # 2. 拼音模糊匹配（处理识别错误）
        variants = expand_variants(text_pinyin.split())

        best_action = "unknown"
        best_score = 0.0
        best_kw = ""

        for variant in variants:
            # 检查每个变体是否匹配某类关键词
            for kw_pinyin in _PASS_KEYWORDS:
                score = self._match_score(variant, kw_pinyin)
                if score > best_score:
                    best_score = score
                    best_action = "pass"
                    best_kw = kw_pinyin

            for kw_pinyin in _FAIL_KEYWORDS:
                score = self._match_score(variant, kw_pinyin)
                if score > best_score:
                    best_score = score
                    best_action = "fail"
                    best_kw = kw_pinyin

            for kw_pinyin in _SKIP_KEYWORDS:
                score = self._match_score(variant, kw_pinyin)
                if score > best_score:
                    best_score = score
                    best_action = "skip"
                    best_kw = kw_pinyin

            for kw_pinyin in _PHOTO_KEYWORDS:
                score = self._match_score(variant, kw_pinyin)
                if score > best_score:
                    best_score = score
                    best_action = "photo"
                    best_kw = kw_pinyin

        # 置信度阈值
        if best_score < 0.4:
            return {"action": "unknown", "confidence": best_score, "note": text, "matched_keyword": ""}

        note = text
        if best_action == "skip":
            note = "不涉及"
        elif best_action == "fail":
            # 尝试提取描述信息
            note = text

        return {
            "action": best_action,
            "confidence": round(best_score, 2),
            "note": note,
            "matched_keyword": best_kw,
        }

    def search_items(self, query: str, items: list[dict]) -> list[dict]:
        """
        拼音模糊搜索检查项。

        参数:
          query: 语音转录文本
          items: 检查项列表 [{"facility": "...", "check_point": "...", "index": 0}, ...]

        返回:
          匹配结果列表（按相似度降序），每项含:
            {"index": int, "facility": str, "check_point": str, "score": float}
        """
        if not query or not query.strip():
            return []

        query_pinyin = self.to_pinyin(query)
        if not query_pinyin:
            return []

        # 原始中文子串匹配（高权重）
        results = []
        q_lower = query.strip().lower()

        for item in items:
            facility = (item.get('facility') or '').lower()
            check_point = (item.get('check_point') or '').lower()
            score = 0.0

            # 精确中文匹配（最高权重: 0.9-1.0）
            if q_lower in facility:
                score = max(score, 0.95)
            elif q_lower in check_point:
                score = max(score, 0.90)

            # 拼音匹配
            facility_py = self.to_pinyin(facility)
            check_point_py = self.to_pinyin(check_point)

            # 词级别Jaccard
            q_words = set(query_pinyin.split())
            f_words = set(facility_py.split())
            c_words = set(check_point_py.split())

            for target_words, weight in [(f_words, 0.85), (c_words, 0.80)]:
                if q_words and target_words:
                    overlap = len(q_words & target_words)
                    if overlap > 0:
                        jaccard = overlap / len(q_words | target_words)
                        score = max(score, jaccard * weight)

            # 拼音子串匹配（如 "mie huo" 在 "mie huo qi" 中）
            if query_pinyin in facility_py:
                score = max(score, 0.88)
            if query_pinyin in check_point_py:
                score = max(score, 0.83)

            # 模糊编辑距离（处理轻微识别错误）
            py_sim_f = pinyin_similarity(query_pinyin, facility_py)
            py_sim_c = pinyin_similarity(query_pinyin, check_point_py)
            score = max(score, py_sim_f * 0.75, py_sim_c * 0.70)

            if score >= 0.25:
                results.append({
                    "index": item.get('index', 0),
                    "facility": item.get('facility', ''),
                    "check_point": item.get('check_point', ''),
                    "score": round(score, 2),
                })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:30]

    def _match_score(self, variant: str, keyword_pinyin: str) -> float:
        """
        计算一个拼音变体与关键词拼音的匹配分数。

        策略:
          1. 完全包含 → 0.95
          2. 词级别 Jaccard → 0.80
          3. 编辑距离 → 0.65
        """
        # 完全包含
        if keyword_pinyin in variant:
            # 关键词长度占变体长度的比例作为置信度
            ratio = len(keyword_pinyin.replace(' ', '')) / max(len(variant.replace(' ', '')), 1)
            return 0.80 + 0.15 * min(ratio, 1.0)

        # 词级别
        kw_words = set(keyword_pinyin.split())
        var_words = set(variant.split())
        overlap = len(kw_words & var_words)
        if overlap > 0:
            jaccard = overlap / len(kw_words | var_words)
            return 0.65 + 0.20 * jaccard

        # 编辑距离
        edit_sim = 1.0 - _levenshtein(variant, keyword_pinyin) / max(len(variant), len(keyword_pinyin), 1)
        if edit_sim > 0.55:
            return 0.45 + 0.25 * edit_sim

        return 0.0


# 全局单例
_matcher: Optional[FuzzyMatcher] = None


def get_matcher() -> FuzzyMatcher:
    global _matcher
    if _matcher is None:
        _matcher = FuzzyMatcher()
    return _matcher
