"""Shared fixtures for fire-inspect tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.rate_limiter import login_limiter

TEST_USER = "lead1"
TEST_PASSWORD = "123456"


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    """每个测试前清空登录限流状态，避免跨测试的 IP/账号封锁串扰。"""
    login_limiter._attempts.clear()
    login_limiter._blocked.clear()
    yield


@pytest.fixture
def client():
    """Unauthenticated test client."""
    return TestClient(app)


@pytest.fixture
def auth_token(client):
    """Login and return a valid JWT token."""
    resp = client.post("/api/v1/auth/login", json={
        "username": TEST_USER,
        "password": TEST_PASSWORD,
    })
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    data = resp.json()
    return data["data"]["token"]


@pytest.fixture
def auth_headers(auth_token):
    """Authorization headers with valid token."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def auth_client(client, auth_token):
    """Test client with pre-set auth headers."""
    client.headers = {"Authorization": f"Bearer {auth_token}"}
    return client
