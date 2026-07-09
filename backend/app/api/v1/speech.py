"""
语音转文字 API — 基于 faster-whisper (small 模型)
支持: webm, mp4, wav, m4a 等常见音频格式
"""
from __future__ import annotations

import os
import tempfile
import time
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Query
from pydantic import BaseModel

from app.core.fuzzy_match import get_matcher

router = APIRouter()

# 懒加载模型单例
_model: Optional[object] = None
_model_load_error: Optional[str] = None


def _get_model():
    """延迟加载 faster-whisper 模型（首次调用时加载，后续复用）"""
    global _model, _model_load_error
    if _model is not None:
        return _model
    if _model_load_error is not None:
        return None

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        _model_load_error = "faster-whisper 未安装，请运行 pip install faster-whisper"
        return None

    try:
        from app.core.config import settings
        model_path = str(settings.BASE_DIR / "models" / "whisper-small")
        if not os.path.isdir(model_path):
            _model_load_error = f"模型目录不存在: {model_path}"
            return None
        # small 模型: 体积~460MB(CT2格式), 中文CER 4.1%，内存约500MB，2核CPU实时推理
        _model = WhisperModel(model_path, device="cpu", compute_type="int8", local_files_only=True)
        return _model
    except Exception as e:
        _model_load_error = f"模型加载失败: {e}"
        return None


class TranscribeResponse(BaseModel):
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
    error: Optional[str] = None


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    """
    上传音频文件，返回识别文字

    - 支持格式: webm, mp4, wav, m4a, ogg
    - 模型: faster-whisper small（中文优化）
    - 最大文件: 10MB
    """
    t0 = time.time()

    model = _get_model()
    if model is None:
        return TranscribeResponse(
            success=False,
            error=_model_load_error or "模型未就绪",
            elapsed_ms=0,
        )

    # 安全检查
    # 不做严格限制，浏览器上传的 webm 可能是多种 MIME

    # 读取并写入临时文件
    raw = await file.read()
    if len(raw) < 1024:
        return TranscribeResponse(
            success=False,
            error="音频文件太小（<1KB），请重新录音",
            elapsed_ms=int((time.time() - t0) * 1000),
        )
    if len(raw) > 10 * 1024 * 1024:
        return TranscribeResponse(
            success=False,
            error="音频文件超过 10MB 限制",
            elapsed_ms=int((time.time() - t0) * 1000),
        )

    # 根据原始文件名或 MIME 确定扩展名
    suffix = ".webm"
    if file.filename:
        _, ext = os.path.splitext(file.filename)
        if ext in (".wav", ".mp3", ".mp4", ".m4a", ".ogg", ".webm", ".opus"):
            suffix = ext

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(raw)
            tmp_path = f.name

        # faster-whisper 转写
        segments, info = model.transcribe(
            tmp_path,
            language="zh",
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                max_speech_duration_s=20,
                speech_pad_ms=400,
            ),
            initial_prompt="消防监督检查：灭火器、消火栓、自动喷淋、烟感探测器、温感探测器、火灾报警控制器、消防控制室、疏散通道、安全出口、防火门、防火卷帘、应急照明、疏散指示标志、防排烟系统、消防电梯、消防水泵、消防水池、消防电源、发电机、配电房、电气线路、燃气管道、消防车道、登高操作场地。合格、不合格、有隐患、过期、损坏、缺失、堵塞、故障、失效、不涉及。",
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
        )

        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())

        # 繁→简 后处理安全网 (opencc)
        try:
            import opencc
            cc = opencc.OpenCC('t2s')
            text = cc.convert(text)
        except ImportError:
            pass

        elapsed_ms = int((time.time() - t0) * 1000)
        print(f"[Speech] 识别完成: {text[:100]}...  ({elapsed_ms}ms, lang={info.language} p={info.language_probability:.2f})")

        return TranscribeResponse(
            success=True,
            text=text,
            elapsed_ms=elapsed_ms,
        )

    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        print(f"[Speech] 转写失败: {e}")
        return TranscribeResponse(
            success=False,
            error=f"语音转写失败: {e}",
            elapsed_ms=elapsed_ms,
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.post("/fuzzy-judge", response_model=FuzzyJudgeResponse)
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
        # 加载对应场景的检查项（从 fire_rules.json）
        import json
        import os
        rules_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'fire_rules.json')
        checklist_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'checklist_config.json')

        items = []
        # 优先从 fire_rules.json 提取（218条规则，含 scene 标签）
        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                rules_data = json.load(f)
            all_rules = rules_data.get('rules', [])
            for i, rule in enumerate(all_rules):
                rule_scenes = rule.get('scene', [])
                # scene 可能是字符串列表或逗号分隔
                if isinstance(rule_scenes, str):
                    rule_scenes = [s.strip() for s in rule_scenes.split(',')]
                if scene in rule_scenes or not rule_scenes:
                    facility = rule.get('title', '') or rule.get('category', '')
                    check_point = rule.get('check_point', '') or rule.get('text', '')[:80]
                    items.append({
                        "index": i,
                        "facility": facility,
                        "check_point": check_point,
                    })

        # 如果 fire_rules.json 没有匹配，回退到 checklist_config.json
        if not items and os.path.exists(checklist_path):
            with open(checklist_path, 'r', encoding='utf-8') as f:
                checklist = json.load(f)
            scene_data = checklist.get('scenes', {}).get(scene, {})
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


@router.get("/health")
async def speech_health():
    """检查语音服务状态"""
    model = _get_model()
    return {
        "status": "ok" if model else "unavailable",
        "model": "faster-whisper small",
        "error": _model_load_error,
    }
