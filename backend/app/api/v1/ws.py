"""
WebSocket 实时协办服务
─────────────────────
主办判定 → 广播给协办端。双向拍照。协办确认 → 生成报告。
单人模式（无协办）→ 不连 WebSocket，独立完成。

协议:
  连接: ws://host/api/v1/ws/{inspection_id}?token={jwt}

→ 服务端推送:
  {"type":"judgment","item_index":5,"result":"pass","from_role":"lead","judged_count":15}
  {"type":"photo","item_index":8,"url":"/static/xxx.jpg","from_role":"lead"}
  {"type":"request_confirm","from_role":"lead"}     ← 主办提请完成
  {"type":"confirmed","from_role":"assist"}          ← 协办确认
  {"type":"user_joined","uid":1,"role":"lead","room_size":2}
  {"type":"user_left","uid":2,"role":"assist","room_size":1}
"""

from __future__ import annotations

import json
import time
import hmac
import base64
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

router = APIRouter()

# 房间: {inspection_id: [{ws, uid, role, is_participant, joined_at}]}
_rooms: Dict[str, List[dict]] = {}


def _decode_token(token: str) -> dict | None:
    """解码 JWT（复刻 auth.py）"""
    try:
        payload_b64 = token.split('.')[1]
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return None


def ws_broadcast(inspection_id: str, event: dict):
    """从 REST API 调用：向房间广播"""
    import asyncio, threading

    async def _send():
        room = _rooms.get(inspection_id, [])
        if not room:
            print(f'[WS-BROADCAST] room {inspection_id} is empty', flush=True)
            return
        print(f'[WS-BROADCAST] sending to {len(room)} clients in {inspection_id}', flush=True)
        alive = []
        for i, entry in enumerate(room):
            try:
                await entry['ws'].send_json(event)
                alive.append(entry)
                print(f'[WS-BROADCAST] sent to client {i+1}/{len(room)}: uid={entry.get("uid","?")}', flush=True)
            except Exception as ex:
                print(f'[WS-BROADCAST] client {i+1} error: {ex}', flush=True)
        if inspection_id in _rooms:
            _rooms[inspection_id] = alive
        print(f'[WS-BROADCAST] done: {len(alive)}/{len(room)} delivered', flush=True)

    def _run_in_thread():
        try:
            asyncio.run(_send())
        except Exception as ex:
            print(f'[WS-BROADCAST] _run_in_thread error: {ex}', flush=True)

    # 在新线程中运行 async send（避免 event loop 冲突）
    t = threading.Thread(target=_run_in_thread, daemon=True)
    t.start()
    # 等待最多2秒
    t.join(timeout=2)


@router.websocket("/{inspection_id}")
async def ws_collaborate(websocket: WebSocket, inspection_id: str, token: str = Query(...)):
    # ── 1. 认证 ──
    payload = _decode_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    uid = payload.get('uid', 0)
    role = payload.get('role', '')

    # ── 2. 验证用户属于该检查 ──
    from app.db.storage import get_inspection
    insp = get_inspection(inspection_id)
    if not insp:
        await websocket.close(code=4004, reason="Inspection not found")
        return

    lead_id = insp.get('lead_id', 0)
    assist_id = insp.get('assist_id', 0)
    is_participant = (uid == lead_id or uid == assist_id)
    is_observer = role in ('admin', 'chief')

    if not is_participant and not is_observer:
        await websocket.close(code=4003, reason="Not authorized")
        return

    # ── 3. 加入房间 ──
    await websocket.accept()

    entry = {'ws': websocket, 'uid': uid, 'role': role, 'joined_at': time.time()}

    if inspection_id not in _rooms:
        _rooms[inspection_id] = []
    _rooms[inspection_id].append(entry)

    role_cn = {'lead': '主办', 'assist': '协办', 'chief': '大队长', 'admin': '管理员'}.get(role, role)
    await _broadcast(inspection_id, {
        'type': 'user_joined',
        'uid': uid,
        'display': f'{role_cn}#{uid}',
        'role': role,
        'room_size': len(_rooms[inspection_id]),
    }, exclude_ws=websocket)

    print(f'[WS] {role_cn}#{uid} joined {inspection_id} (room={len(_rooms[inspection_id])})')

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get('type', '')

            if msg_type == 'ping':
                await websocket.send_json({'type': 'pong'})

            elif msg_type == 'photo':
                await _broadcast(inspection_id, {
                    'type': 'photo',
                    'item_index': data.get('item_index', 0),
                    'url': data.get('url', ''),
                    'from_uid': uid,
                    'from_role': role,
                }, exclude_ws=websocket)

            elif msg_type == 'jump':
                await _broadcast(inspection_id, {
                    'type': 'jump',
                    'target_index': data.get('target_index', 0),
                    'from_uid': uid,
                    'from_role': role,
                }, exclude_ws=websocket)

            elif msg_type == 'request_confirm':
                # 主办提请完成 → 通知协办确认
                await _broadcast(inspection_id, {
                    'type': 'request_confirm',
                    'from_uid': uid,
                    'from_role': role,
                    'total_items': data.get('total_items', 0),
                    'judged_count': data.get('judged_count', 0),
                    'fail_count': data.get('fail_count', 0),
                })

            elif msg_type == 'confirm':
                # 协办确认 → 通知主办
                await _broadcast(inspection_id, {
                    'type': 'confirmed',
                    'from_uid': uid,
                    'from_role': role,
                })

    except WebSocketDisconnect:
        pass
    finally:
        if inspection_id in _rooms:
            _rooms[inspection_id] = [e for e in _rooms[inspection_id] if e['ws'] is not websocket]
            if not _rooms[inspection_id]:
                del _rooms[inspection_id]
            else:
                await _broadcast(inspection_id, {
                    'type': 'user_left',
                    'uid': uid,
                    'role': role,
                    'room_size': len(_rooms.get(inspection_id, [])),
                })

        print(f'[WS] {role_cn}#{uid} left {inspection_id}')


async def _broadcast(inspection_id: str, event: dict, exclude_ws=None):
    """广播给房间内所有客户端"""
    room = _rooms.get(inspection_id, [])
    for entry in room:
        if entry['ws'] is exclude_ws:
            continue
        try:
            await entry['ws'].send_json(event)
        except Exception:
            pass
