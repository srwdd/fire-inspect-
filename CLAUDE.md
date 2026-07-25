# FireAgent — 消防安全巡检多模态智能体

图片 → VLM 视觉事实抽取 → 消防法规 RAG（证据树检索）→ 证据约束的风险结论 + 整改建议。

## 结构

- `backend/` — FastAPI + SQLAlchemy + SQLite。核心管线在 `backend/app/services/`（analyzer 两跳推理、retriever 混合检索、memory 四层记忆）；API 在 `backend/app/api/v1/`
- `web/` — 现役 Web 端（静态 H5 + Vue3 CDN，由后端 mount 到 `/web`）。主 JS 是 `app_v176.js`
- `pages/` + 根目录 `app.js/app.json/utils/` — 微信小程序端（开发态，`utils/config.js` 后端地址写死 127.0.0.1，无登录流程）
- `docs/ALGORITHMS.md` — 方法论文档

## 必读：当前状态

**先读 `FIRE_FIX_20260725.md`** — 2026-07-25 安全止血修复的完整日志：改了什么、为什么、部署注意事项、以及尚未修复的问题清单（评测体系金标泄漏、guardrail 死代码、双数据库分裂等）。后续任何改动前请确认不与该日志冲突；完成新阶段工作后请更新它或追加新日志。

## 测试

```bash
cd backend && python -m pytest tests/ --ignore=tests/test_e2e.py -q
```

- 测试依赖本地 `backend/fire_inspect.db`（gitignore，含播种的测试账号 admin/admin123、lead1/123456）
- `tests/test_e2e.py` 默认打生产站 `https://ai-bang.top`，本地不要跑
- 安全回归用例在 `tests/test_security.py`：改任何认证/鉴权逻辑后必须保持全绿

## 关键约束

- **所有付费 LLM 端点必须要求登录**（2026-07 前曾全部裸奔，API key 可被任意盗刷）。新增端点默认加 `Depends(get_current_user)`，写操作按角色用 `require_admin`
- JWT 密钥只从 `JWT_SECRET` 环境变量读，禁止恢复硬编码默认值
- 知识库 canonical 文件在 `backend/fire_rules.json` 和 `backend/app/data/fire_rules.json`，根目录旧副本已删除，不要重建
- `frontend/` 旧目录已删除（僵尸代码），Web 端只改 `web/`
