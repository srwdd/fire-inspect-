"""检查工作流端到端回归测试（2026-07-27 新增）。

覆盖生产上真实炸过的两个 bug：
1. submit_judge 调用未导入的 precipitate_finding -> NameError 500
   （远端 b0d7770 加调用漏 import，且沉淀失败不应阻断判定）
2. DELETE /inspection/{id} 违反 FK（rectifications 未先删）-> 500
"""
import pytest


@pytest.fixture
def workflow_id(auth_headers, client, tmp_path, monkeypatch):
    """创建 hotel/daily 检查单，测试后清理；案例沉淀重定向到临时目录防污染仓库。"""
    import app.services.case_precipitate as cp
    monkeypatch.setattr(cp, "CASES_PATH", tmp_path / "fire_cases.json")
    resp = client.post("/api/v1/inspection/start", headers=auth_headers, json={
        "venue_type": "hotel", "inspection_type": "daily",
        "location": "回归测试酒店", "lead_id": 3,
    })
    assert resp.status_code == 200, resp.json()
    data = resp.json()["data"]
    assert data["total_items"] > 0
    yield data["inspection_id"]
    client.delete(f"/api/v1/inspection/{data['inspection_id']}", headers=auth_headers)


class TestInspectionWorkflow:
    def test_full_workflow(self, client, auth_headers, workflow_id):
        insp = workflow_id

        # 检查项
        resp = client.get(f"/api/v1/inspection/{insp}/items", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        items = data.get("items", data) if isinstance(data, dict) else data
        assert len(items) > 0

        # 合格判定
        resp = client.post(f"/api/v1/inspection/{insp}/judge", headers=auth_headers,
                           json={"item_index": 0, "result": "pass", "note": "回归测试 pass"})
        assert resp.status_code == 200, resp.json()

        # 不合格判定（触发案例沉淀 + 整改单，曾是 NameError/FK 现场）
        resp = client.post(f"/api/v1/inspection/{insp}/judge", headers=auth_headers,
                           json={"item_index": 1, "result": "fail", "note": "回归测试：模拟不合格项"})
        assert resp.status_code == 200, resp.json()

        # 报告
        resp = client.get(f"/api/v1/inspection/{insp}/report", headers=auth_headers)
        assert resp.status_code == 200

        # 删除（含 findings + rectifications 级联，曾是 FK 500）
        resp = client.delete(f"/api/v1/inspection/{insp}", headers=auth_headers)
        assert resp.status_code == 200, resp.json()

        # 已删除
        resp = client.get(f"/api/v1/inspection/{insp}/items", headers=auth_headers)
        assert resp.status_code in (400, 404)

    def test_judge_requires_auth(self, client, workflow_id):
        resp = client.post(f"/api/v1/inspection/{workflow_id}/judge",
                           json={"item_index": 0, "result": "pass", "note": "x"})
        assert resp.status_code == 401
