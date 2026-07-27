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


class TestCompleteInspection:
    """完成状态回写（2026-07-27）：全部判定后才能 complete，且状态落库。"""

    def test_complete_partial_rejected(self, client, auth_headers, workflow_id):
        resp = client.post(f"/api/v1/inspection/{workflow_id}/complete", headers=auth_headers)
        assert resp.status_code == 400
        assert "未判定" in str(resp.json().get("detail", ""))

    def test_complete_after_all_judged(self, client, auth_headers, workflow_id):
        insp = workflow_id
        # 判完所有项
        resp = client.get(f"/api/v1/inspection/{insp}/items", headers=auth_headers)
        items = resp.json()["data"]
        for i in range(len(items)):
            r = client.post(f"/api/v1/inspection/{insp}/judge", headers=auth_headers,
                            json={"item_index": i, "result": "pass", "note": "t"})
            assert r.status_code == 200
        # 完成
        resp = client.post(f"/api/v1/inspection/{insp}/complete", headers=auth_headers)
        assert resp.status_code == 200
        # 重复完成 → already
        resp = client.post(f"/api/v1/inspection/{insp}/complete", headers=auth_headers)
        assert resp.status_code == 200 and resp.json().get("already") is True
        # 已完成的检查不能再删除
        resp = client.delete(f"/api/v1/inspection/{insp}", headers=auth_headers)
        assert resp.status_code == 400
        # 完成后出现在最近完成列表（active?include_completed=1）
        resp = client.get("/api/v1/inspection/active?include_completed=1", headers=auth_headers)
        completed = [x for x in resp.json()["data"] if x["inspection_id"] == insp and x["status"] == "completed"]
        assert len(completed) == 1
