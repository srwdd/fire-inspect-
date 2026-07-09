"""更新 speech.py: 添加模糊匹配 API + Whisper 消防词汇提示"""
import re

with open('/opt/fire-inspect/backend/app/api/v1/speech.py', 'r', encoding='utf-8') as f:
    code = f.read()

changes = 0

# ── 1. 导入 FuzzyMatcher ──
old = 'from fastapi import APIRouter, File, UploadFile\nfrom pydantic import BaseModel'
new = '''from fastapi import APIRouter, File, UploadFile, Query
from pydantic import BaseModel

from app.core.fuzzy_match import get_matcher'''

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print('1. 添加 FuzzyMatcher 导入')

# ── 2. 添加模糊匹配的 Pydantic 模型（在 TranscribeResponse 之后） ──
old = 'class TranscribeResponse(BaseModel):\n    success: bool = True\n    text: str = ""\n    error: Optional[str] = None\n    elapsed_ms: int = 0'
new = '''class TranscribeResponse(BaseModel):
    success: bool = True
    text: str = ""
    error: Optional[str] = None
    elapsed_ms: int = 0


class FuzzyJudgeResponse(BaseModel):
    success: bool = True
    text: str = ""
    action: str = "unknown"
    confidence: float = 0.0
    note: str = ""
    matched_keyword: str = ""
    error: Optional[str] = None


class FuzzySearchResponse(BaseModel):
    success: bool = True
    query: str = ""
    results: list = []
    count: int = 0
    error: Optional[str] = None'''

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print('2. 添加响应模型')

# ── 3. 优化 Whisper initial_prompt 加入消防词汇 ──
old = 'initial_prompt="以下是简体中文普通话的句子。"'
new = '''initial_prompt="消防监督检查：灭火器、消火栓、自动喷淋、烟感探测器、温感探测器、火灾报警控制器、消防控制室、疏散通道、安全出口、防火门、防火卷帘、应急照明、疏散指示标志、防排烟系统、消防电梯、消防水泵、消防水池、消防电源、发电机、配电房、电气线路、燃气管道、消防车道、登高操作场地。合格、不合格、有隐患、过期、损坏、缺失、堵塞、故障、失效、不涉及。"'''

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print('3. 优化 Whisper initial_prompt（消防词汇）')

# ── 4. 在 health endpoint 之前添加模糊匹配路由 ──
old = '@router.get("/health")'
new = '''@router.post("/fuzzy-judge", response_model=FuzzyJudgeResponse)
async def fuzzy_judge(text: str = Query(..., description="语音转录文本")):
    """
    对语音转录文本进行模糊判定分类。

    支持：
    - 精确中文匹配（合格/不合格/跳过/拍照）
    - 拼音容错匹配（处理口音和识别错误）
    - 南方口音混淆展开（zh/z, sh/s, ch/c, n/l, -n/-ng, r/l, h/f）

    返回 action: pass | fail | skip | photo | unknown
    """
    if not text or not text.strip():
        return FuzzyJudgeResponse(success=False, error="文本为空")

    try:
        fm = get_matcher()
        result = fm.classify_judgment(text)
        return FuzzyJudgeResponse(
            success=True,
            text=text,
            action=result["action"],
            confidence=result["confidence"],
            note=result["note"],
            matched_keyword=result["matched_keyword"],
        )
    except Exception as e:
        return FuzzyJudgeResponse(success=False, error=str(e))


@router.post("/fuzzy-search", response_model=FuzzySearchResponse)
async def fuzzy_search(
    text: str = Query(..., description="语音转录文本"),
    scene: str = Query("hotel", description="场所类型: hotel/mall/entertainment/school/hospital/elderly/warehouse/office/underground"),
):
    """
    对语音转录文本进行模糊搜索，返回匹配的检查项列表。

    返回按相似度降序排列，每项含:
      - index: 检查项序号
      - facility: 设施名称
      - check_point: 检查要点
      - score: 匹配分数 (0~1)
    """
    if not text or not text.strip():
        return FuzzySearchResponse(success=False, error="文本为空")

    try:
        # 加载对应场景的检查项
        import json
        import os
        checklist_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'checklist_config.json')
        # checklist_config 不直接含检查项，我们直接从 fire_rules.json 提取
        rules_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'fire_rules.json')

        items = []
        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            # fire_rules.json 结构: {"scenes": {"hotel": {"items": [...]}, ...}}
            scene_data = rules.get('scenes', {}).get(scene, {})
            scene_items = scene_data.get('items', [])
            for i, item in enumerate(scene_items):
                items.append({
                    "index": i,
                    "facility": item.get('facility', ''),
                    "check_point": item.get('check_point', ''),
                })

        if not items:
            return FuzzySearchResponse(success=False, error=f"未找到场景 '{scene}' 的检查项")

        fm = get_matcher()
        results = fm.search_items(text, items)
        return FuzzySearchResponse(
            success=True,
            query=text,
            results=results,
            count=len(results),
        )
    except Exception as e:
        return FuzzySearchResponse(success=False, error=str(e))


@router.get("/health")'''

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print('4. 添加 /fuzzy-judge 和 /fuzzy-search 端点')

with open('/opt/fire-inspect/backend/app/api/v1/speech.py', 'w', encoding='utf-8') as f:
    f.write(code)

print(f'完成: {changes}/4 处修改')
