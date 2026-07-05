"""兼容性 shim — re-export from app.core.checklist_engine.

Canonical 实现在 app/core/checklist_engine.py 中。
此文件仅为向后兼容保留，所有新 import 应使用 app.core.checklist_engine。
"""
from app.core.checklist_engine import (  # noqa: F401
    ChecklistEngine,
    checklist_engine,
    _normalize_source_type,
    _parse_article_num,
    SOURCE_FULL_NAMES,
    SOURCE_TYPE_PRIORITY,
)
