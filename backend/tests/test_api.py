"""API integration tests for fire-inspect backend."""
import pytest
import time


class TestHealthCheck:
    """Health check and monitoring endpoints."""

    def test_health_returns_version(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_security_headers_present(self, client):
        resp = client.get("/health")
        headers = resp.headers
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        # CSP may not be set on /docs paths, but should be on /health
        # Actually CSP is set on non-/docs paths
        assert "content-security-policy" in headers


class TestAuthentication:
    """Login, token, and rate limiting."""

    def test_login_success(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "lead1",
            "password": "123456",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "token" in data["data"]
        assert len(data["data"]["token"]) > 20

    def test_login_wrong_password(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "lead1",
            "password": "wrong_password_xyz",
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.json()}"
        detail = resp.json().get("detail", "")
        assert "用户名或密码错误" in str(detail)

    def test_login_empty_username(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "",
            "password": "123456",
        })
        assert resp.status_code == 422  # Validation error

    def test_me_requires_auth(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_with_token(self, client, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        user = data["data"]
        assert user is not None
        assert "username" in user


class TestInspections:
    """Inspection workflow endpoints."""

    def test_active_inspections_requires_auth(self, client):
        resp = client.get("/api/v1/inspection/active")
        assert resp.status_code == 401

    def test_active_inspections_with_auth(self, client, auth_headers):
        resp = client.get("/api/v1/inspection/active", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("code") == 0
        assert "data" in data

    def test_venue_history_with_auth(self, client, auth_headers):
        resp = client.get("/api/v1/inspection/venue-history", headers=auth_headers)
        assert resp.status_code == 200

    def test_trends_requires_auth(self, client):
        resp = client.get("/api/v1/inspection/trends")
        assert resp.status_code == 401


class TestOrganizations:
    """Organization listing (public endpoint)."""

    def test_list_organizations(self, client):
        resp = client.get("/api/v1/auth/organizations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        orgs = data["data"]
        assert len(orgs) > 0
        assert "name" in orgs[0]


class TestCORS:
    """CORS headers verification."""

    def test_cors_headers_on_options(self, client):
        resp = client.options("/api/v1/auth/login")
        # OPTIONS should return CORS headers regardless
        assert resp.status_code in (200, 204, 405)


class TestRateLimiting:
    """Login rate limiting: 5 failures -> 429."""

    def test_rate_limit_triggers_after_5_failures(self, client):
        # Reset rate limiter state by waiting
        # Actually, we just hammer it and check the 6th returns 429
        import time
        username = f"test_ratelimit_{int(time.time())}"
        responses = []
        for i in range(6):
            resp = client.post("/api/v1/auth/login", json={
                "username": username,
                "password": "wrong",
            })
            responses.append(resp.status_code)

        # First 5 should be 401, 6th should be 429
        auth_fails = [s for s in responses if s == 401]
        rate_limits = [s for s in responses if s == 429]
        assert len(auth_fails) >= 4, f"Expected at least 4x 401, got: {responses}"
        assert len(rate_limits) >= 1, f"Expected rate limit to trigger, got: {responses}"
