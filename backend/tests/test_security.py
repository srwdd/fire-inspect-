"""Security regression tests for the 2026-07 hardening round.

Covers:
- Paid/LLM and destructive endpoints reject anonymous requests (401)
- Role enforcement: non-admin cannot create users / wipe records (403)
- JWT: tampered signature and expired token are rejected
- /auth/me returns real DB-backed values (not empty fields)
- WebSocket rejects invalid tokens with close code 4001
"""
import base64
import hashlib
import hmac
import json
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.v1.auth import SECRET


# ── helpers ─────────────────────────────────────────────

def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"login {username} failed: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


@pytest.fixture
def lead_headers(client):
    return _login(client, "lead1", "123456")


@pytest.fixture
def admin_headers(client):
    return _login(client, "admin", "admin123")


def _forged_token(uid=1, role="admin", oid=0, exp=None):
    """Craft a token with a WRONG signature (attacker without the secret)."""
    h = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps({
        "uid": uid, "role": role, "oid": oid,
        "exp": exp or int(time.time()) + 3600,
    }).encode()).decode().rstrip("=")
    return f"{h}.{p}.{'0' * 64}"


def _expired_token():
    """Correctly signed but already expired."""
    h = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps({
        "uid": 3, "role": "lead", "oid": 1, "exp": int(time.time()) - 10,
    }).encode()).decode().rstrip("=")
    msg = f"{h}.{p}"
    sig = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}.{sig}"


# ── anonymous access must be rejected ───────────────────

class TestAnonymousRejected:
    """Endpoints that were unauthenticated before the hardening round."""

    @pytest.mark.parametrize("method,path,json_body", [
        ("get", "/api/v1/records/", None),
        ("get", "/api/v1/records/insights", None),
        ("delete", "/api/v1/records/", None),
        ("post", "/api/v1/chat/completions", {"messages": [{"role": "user", "content": "hi"}]}),
        ("post", "/api/v1/agent/chat", {"message": "hi"}),
        ("post", "/api/v1/speech/ai-qa", {"question": "x"}),
        ("post", "/api/v1/speech/ai-judge", {"voice_text": "x"}),
        ("post", "/api/v1/speech/ai-summary", {}),
        ("post", "/api/v1/speech/ai-identify", {"image": "x"}),
        ("post", "/api/v1/speech/ai-compare", {"old_image": "a", "new_image": "b"}),
        ("post", "/api/v1/auth/users", {"username": "hacker", "password": "1234",
                                        "role": "admin", "display_name": "h"}),
        ("get", "/api/v1/auth/users", None),
        ("get", "/api/v1/owner/submissions", None),
        ("post", "/api/v1/owner/create-link", None),
        ("delete", "/api/v1/owner/submissions/OWNER-XXXX", None),
        ("get", "/api/v1/memory/overview", None),
        ("get", "/api/v1/memory/tasks", None),
        ("post", "/api/v1/memory/rebuild-index", None),
        ("get", "/api/v1/inspection/stats", None),
        ("get", "/api/v1/inspection/dashboard-stats", None),
    ])
    def test_anonymous_gets_401(self, client, method, path, json_body):
        resp = getattr(client, method)(path, json=json_body) if json_body is not None \
            else getattr(client, method)(path)
        assert resp.status_code == 401, f"{method.upper()} {path} -> {resp.status_code} (expected 401)"

    def test_analysis_upload_anonymous_401(self, client):
        resp = client.post("/api/v1/analysis/upload",
                           files={"file": ("x.jpg", b"\xff\xd8\xff", "image/jpeg")})
        assert resp.status_code == 401


# ── role enforcement ────────────────────────────────────

class TestRoleEnforcement:
    def test_non_admin_cannot_create_user(self, client, lead_headers):
        resp = client.post("/api/v1/auth/users", headers=lead_headers, json={
            "username": "evil1", "password": "1234", "role": "admin", "display_name": "e"})
        assert resp.status_code == 403

    def test_non_admin_cannot_clear_records(self, client, lead_headers):
        resp = client.delete("/api/v1/records/", headers=lead_headers)
        assert resp.status_code == 403

    def test_admin_can_create_user_and_user_can_login(self, client, admin_headers):
        name = f"sec_test_{int(time.time())}"
        resp = client.post("/api/v1/auth/users", headers=admin_headers, json={
            "username": name, "password": "pass1234", "role": "assist", "display_name": "安全测试"})
        assert resp.status_code == 200, resp.json()
        # new password must be stored as PBKDF2 and work at login
        login = client.post("/api/v1/auth/login", json={"username": name, "password": "pass1234"})
        assert login.status_code == 200

    def test_invalid_role_rejected(self, client, admin_headers):
        resp = client.post("/api/v1/auth/users", headers=admin_headers, json={
            "username": "badrole1", "password": "1234", "role": "superadmin", "display_name": "x"})
        assert resp.status_code == 400


# ── token integrity ─────────────────────────────────────

class TestTokenIntegrity:
    def test_forged_signature_rejected(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {_forged_token()}"})
        assert resp.status_code == 401

    def test_expired_token_rejected(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {_expired_token()}"})
        assert resp.status_code == 401

    def test_ws_invalid_token_closed(self, client):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/ws/some-inspection?token={_forged_token()}"):
                pass
        assert exc_info.value.code == 4001


# ── /auth/me real values ────────────────────────────────

class TestMeEndpoint:
    def test_me_returns_db_values(self, client, lead_headers):
        resp = client.get("/api/v1/auth/me", headers=lead_headers)
        assert resp.status_code == 200
        user = resp.json()["data"]
        assert user["username"] == "lead1"
        assert user["role"] == "lead"
        assert user["id"] == 3
        assert user["display_name"] == "张监督员"
        assert user["org_name"] == "广丰区消防救援大队"


# ── legacy password hash transparent upgrade ────────────

class TestPasswordHashing:
    def test_new_passwords_stored_as_pbkdf2(self):
        from app.api.v1.auth import _hash_pw, _verify_pw
        stored = _hash_pw("secret123")
        assert stored.startswith("pbkdf2$")
        assert _verify_pw("secret123", stored)
        assert not _verify_pw("wrong", stored)

    def test_legacy_sha256_still_verifies(self):
        legacy = hashlib.sha256("123456".encode()).hexdigest()
        from app.api.v1.auth import _verify_pw
        assert _verify_pw("123456", legacy)
        assert not _verify_pw("123457", legacy)
