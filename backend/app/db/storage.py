"""
SQLite 持久化存储 — 替换 inspection_api.py 中的内存 Dict。
API 接口完全兼容，仅替换存储后端。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent.parent / "fire_inspect.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """初始化数据库表（幂等）"""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS inspections (
                id TEXT PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'first',
                venue_type TEXT NOT NULL,
                venue_name TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                inspector TEXT NOT NULL DEFAULT '',
                staff_count INTEGER NOT NULL DEFAULT 0,
                floor_count INTEGER NOT NULL DEFAULT 0,
                area_sqm INTEGER NOT NULL DEFAULT 0,
                staff_sample TEXT,
                floor_sample TEXT,
                total_items INTEGER NOT NULL DEFAULT 0,
                mandatory_count INTEGER NOT NULL DEFAULT 0,
                sample_count INTEGER NOT NULL DEFAULT 0,
                current_index INTEGER NOT NULL DEFAULT 0,
                lead_id INTEGER NOT NULL DEFAULT 0,
                assist_id INTEGER NOT NULL DEFAULT 0,
                org_id INTEGER NOT NULL DEFAULT 0,
                venue_addr TEXT NOT NULL DEFAULT '',
                venue_address TEXT NOT NULL DEFAULT '',
                items_json TEXT NOT NULL DEFAULT '[]',
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL DEFAULT 'in_progress',
                previous_inspection_id TEXT,
                previous_fail_ids TEXT NOT NULL DEFAULT '[]'
            );


            CREATE TABLE IF NOT EXISTS owner_submissions (
                code TEXT PRIMARY KEY,
                venue_type TEXT NOT NULL,
                venue_name TEXT NOT NULL DEFAULT '',
                venue_address TEXT NOT NULL DEFAULT '',
                contact_name TEXT NOT NULL DEFAULT '',
                contact_phone TEXT NOT NULL DEFAULT '',
                inspector_id INTEGER NOT NULL DEFAULT 0,
                org_id INTEGER NOT NULL DEFAULT 0,
                items_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                submitted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inspection_id TEXT NOT NULL,
                item_index INTEGER NOT NULL,
                rule_id TEXT NOT NULL,
                facility TEXT NOT NULL DEFAULT '',
                check_point TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                severity TEXT NOT NULL DEFAULT 'normal',
                is_mandatory INTEGER NOT NULL DEFAULT 0,
                result TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                judge_source TEXT NOT NULL DEFAULT 'manual',
                rectification_status TEXT NOT NULL DEFAULT '',
                photos TEXT NOT NULL DEFAULT '[]',
                judged_at TEXT NOT NULL,
                FOREIGN KEY (inspection_id) REFERENCES inspections(id)
            );

            CREATE INDEX IF NOT EXISTS idx_findings_inspection
                ON findings(inspection_id);
        """)
        # 迁移：旧表可能没有 photos 列
        try:
            conn.execute("ALTER TABLE findings ADD COLUMN photos TEXT NOT NULL DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass  # 列已存在


# ── Inspection CRUD ──────────────────────────────────

def save_inspection(state: Dict[str, Any]) -> None:
    """创建或更新检查记录"""
    items_json = json.dumps(state.get("items", []), ensure_ascii=False)
    staff_sample = json.dumps(state.get("staff_sample"), ensure_ascii=False) if state.get("staff_sample") else None
    floor_sample = json.dumps(state.get("floor_sample"), ensure_ascii=False) if state.get("floor_sample") else None
    prev_fail_ids = json.dumps(state.get("previous_fail_ids", []), ensure_ascii=False)

    with _connect() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO inspections (
                id, mode, venue_type, venue_name, location, inspector,
                staff_count, floor_count, area_sqm,
                staff_sample, floor_sample,
                total_items, mandatory_count, sample_count,
                current_index, lead_id, assist_id, org_id, venue_addr, venue_address,
                items_json,
                started_at, completed_at, status,
                previous_inspection_id, previous_fail_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state["inspection_id"],
            state.get("mode", "first"),
            state.get("venue_type", ""),
            state.get("venue_name", ""),
            state.get("location", ""),
            state.get("inspector", ""),
            state.get("staff_count", 0),
            state.get("floor_count", 0),
            state.get("area_sqm", 0),
            staff_sample,
            floor_sample,
            state.get("total_items", 0),
            state.get("mandatory_count", 0),
            state.get("sample_count", 0),
            state.get("current_index", 0),
            state.get("lead_id", 0),
            state.get("assist_id", 0),
            state.get("org_id", 0),
            state.get("venue_addr", ""),
            state.get("venue_address", ""),
            items_json,
            state.get("started_at", datetime.now().isoformat()),
            state.get("completed_at"),
            state.get("status", "in_progress"),
            state.get("previous_inspection_id"),
            prev_fail_ids,
        ))


def get_inspection(inspection_id: str) -> Optional[Dict[str, Any]]:
    """获取单个检查记录"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM inspections WHERE id = ?", (inspection_id,)
        ).fetchone()
    if not row:
        return None
    return _row_to_state(row)


def update_inspection_status(inspection_id: str, status: str) -> None:
    """更新检查状态"""
    with _connect() as conn:
        if status == "completed":
            conn.execute(
                "UPDATE inspections SET status = ?, completed_at = ? WHERE id = ?",
                (status, datetime.now().isoformat(), inspection_id),
            )
        else:
            conn.execute(
                "UPDATE inspections SET status = ? WHERE id = ?",
                (status, inspection_id),
            )


def update_current_index(inspection_id: str, index: int) -> None:
    """更新当前检查项索引"""
    with _connect() as conn:
        conn.execute(
            "UPDATE inspections SET current_index = ? WHERE id = ?",
            (index, inspection_id),
        )


def search_inspections(venue_name: str = "") -> List[Dict[str, Any]]:
    """搜索已完成的检查记录"""
    with _connect() as conn:
        if venue_name:
            rows = conn.execute(
                "SELECT * FROM inspections WHERE status = 'completed' AND venue_name LIKE ? ORDER BY started_at DESC",
                (f"%{venue_name}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM inspections WHERE status = 'completed' ORDER BY started_at DESC",
            ).fetchall()
    return [_row_to_state(r) for r in rows]



def list_active_inspections(uid: int = 0) -> List[Dict[str, Any]]:
    """列出进行中的检查（可按用户过滤）"""
    with _connect() as conn:
        if uid > 0:
            rows = conn.execute(
                "SELECT * FROM inspections WHERE status = 'in_progress' AND (lead_id = ? OR assist_id = ?) ORDER BY started_at DESC",
                (uid, uid),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM inspections WHERE status = 'in_progress' ORDER BY started_at DESC",
            ).fetchall()
    return [_row_to_state(r) for r in rows]


def list_recent_completed(org_id: int = 0, limit: int = 5) -> List[Dict[str, Any]]:
    """列出最近完成的检查（7天内）"""
    with _connect() as conn:
        if org_id > 0:
            rows = conn.execute(
                "SELECT * FROM inspections WHERE status = 'completed' AND org_id = ? AND date(completed_at) >= date('now', '-7 days') ORDER BY completed_at DESC LIMIT ?",
                (org_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM inspections WHERE status = 'completed' AND date(completed_at) >= date('now', '-7 days') ORDER BY completed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [_row_to_state(r) for r in rows]


def create_owner_submission(code, venue_type, venue_name, venue_address, inspector_id, org_id):
    with _connect() as conn:
        conn.execute(
            """INSERT INTO owner_submissions (code, venue_type, venue_name, venue_address, inspector_id, org_id, items_json, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (code, venue_type, venue_name, venue_address, inspector_id, org_id, '[]', 'draft', datetime.now().isoformat())
        )
        conn.commit()

def get_owner_submission(code):
    with _connect() as conn:
        row=conn.execute("SELECT * FROM owner_submissions WHERE code=?",(code,)).fetchone()
        if not row: return None
        d=dict(row)
        d['items']=json.loads(d.pop('items_json','[]'))
        return d

def update_owner_item(code, item_index, data):
    with _connect() as conn:
        row=conn.execute("SELECT items_json FROM owner_submissions WHERE code=?",(code,)).fetchone()
        if not row: return
        items=json.loads(row[0])
        while len(items) <= item_index:
            items.append({})
        items[item_index]=data
        conn.execute("UPDATE owner_submissions SET items_json=? WHERE code=?",(json.dumps(items,ensure_ascii=False),code))
        conn.commit()

def submit_owner(code):
    with _connect() as conn:
        conn.execute("UPDATE owner_submissions SET status='submitted', submitted_at=? WHERE code=?",(datetime.now().isoformat(),code))
        conn.commit()

def list_owner_submissions(org_id=0):
    with _connect() as conn:
        if org_id:
            rows=conn.execute("SELECT * FROM owner_submissions WHERE org_id=? ORDER BY created_at DESC",(org_id,)).fetchall()
        else:
            rows=conn.execute("SELECT * FROM owner_submissions ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

def update_owner_status(code, status):
    with _connect() as conn:
        conn.execute("UPDATE owner_submissions SET status=? WHERE code=?",(status,code))
        conn.commit()

def update_owner_return(code, reason=""):
    with _connect() as conn:
        conn.execute("UPDATE owner_submissions SET status='returned', return_reason=? WHERE code=?",(reason,code))
        conn.commit()

def _row_to_state(row: sqlite3.Row) -> Dict[str, Any]:
    """将数据库行转换回 state dict"""
    d = dict(row)
    # 安全 JSON 解析辅助
    def _safe_json(v, default=None):
        if not v or not isinstance(v, str) or v.strip() == '':
            return default if default is not None else []
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else []
    # 还原 JSON 字段
    d["items"] = _safe_json(d.pop("items_json", "[]"))
    d["inspection_id"] = d.pop("id")
    d["staff_sample"] = _safe_json(d.get("staff_sample"), None)
    d["floor_sample"] = _safe_json(d.get("floor_sample"), None)
    d["previous_fail_ids"] = _safe_json(d.get("previous_fail_ids", "[]"))
    return d


# ── Findings CRUD ────────────────────────────────────

def save_finding(inspection_id: str, finding: Dict[str, Any]) -> None:
    """保存单条检查发现"""
    photos = json.dumps(finding.get("photos", []), ensure_ascii=False)
    with _connect() as conn:
        conn.execute("""
            INSERT INTO findings (
                inspection_id, item_index, rule_id, facility, check_point,
                category, severity, is_mandatory,
                result, note, judge_source, rectification_status, photos, judged_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inspection_id,
            finding.get("item_index", 0),
            finding.get("rule_id", ""),
            finding.get("facility", ""),
            finding.get("check_point", ""),
            finding.get("category", ""),
            finding.get("severity", "normal"),
            1 if finding.get("is_mandatory") else 0,
            finding.get("result", ""),
            finding.get("note", ""),
            finding.get("judge_source", "manual"),
            finding.get("rectification_status", ""),
            photos,
            finding.get("judged_at", datetime.now().isoformat()),
        ))


def add_finding_photo(inspection_id: str, item_index: int, filename: str) -> None:
    """给发现追加照片（不存在时先创建占位行）"""
    with _connect() as conn:
        # 确保行存在（拍照可能在判断之前）
        existing = conn.execute(
            "SELECT photos FROM findings WHERE inspection_id = ? AND item_index = ?",
            (inspection_id, item_index),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO findings (inspection_id, item_index, rule_id, result, photos, judged_at) VALUES (?, ?, ?, ?, ?, ?)",
                (inspection_id, item_index, "", "pending", json.dumps([filename]), datetime.now().isoformat()),
            )
        else:
            current = json.loads(existing["photos"] or "[]")
            current.append(filename)
            conn.execute(
                "UPDATE findings SET photos = ? WHERE inspection_id = ? AND item_index = ?",
                (json.dumps(current, ensure_ascii=False), inspection_id, item_index),
            )


def get_findings(inspection_id: str) -> List[Dict[str, Any]]:
    """获取检查的所有发现"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM findings WHERE inspection_id = ? ORDER BY item_index",
            (inspection_id,),
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["photos"] = json.loads(d.get("photos", "[]"))
        results.append(d)
    return results


# ── 初始化 ───────────────────────────────────────────
init_db()
