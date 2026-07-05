"""
语音转文字 API — 基于 faster-whisper (small 模型)
支持: webm, mp4, wav, m4a 等常见音频格式
"""
from __future__ import annotations

import os
import tempfile
import time
from typing import Optional

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

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
            initial_prompt="以下是简体中文普通话的句子。",
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


@router.get("/health")
async def speech_health():
    """检查语音服务状态"""
    model = _get_model()
    return {
        "status": "ok" if model else "unavailable",
        "model": "faster-whisper small",
        "error": _model_load_error,
    }
