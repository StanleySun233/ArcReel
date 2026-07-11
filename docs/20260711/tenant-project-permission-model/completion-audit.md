# Completion Audit: tenant/user/project goal

**Date:** 20260711  
**Status:** remote model path verified; ArcReel video path reaches CaMeL provider failure; full legacy pytest still not green
**Scope:** 用户原始目标逐项审计。只以当前 ArcReel 工作树、测试输出、运行记录和文档为证据；不包含 `../camel-api`。

## 结论

当前核心商业化改造目标已经完成到可远程验证状态；剩余风险是全量历史测试套件仍不绿，不能把“所有 legacy tests 全绿”作为已完成事实。

已完成并有证据的部分：

- 开发文档构建完成。
- 旧错误开发文档已删除或降级为审计记录。
- 最终租户、用户、项目三层关系和权限限制已交付。
- SQLite / 本地文件数据库旧方案已下掉。
- Issued Tokens 已按要求禁用，但保留业务代码。
- PostgreSQL-only、tenant/project id、role refresh、owner/admin/member/view 权限、项目删除权限、用量 project_id、session/task project_id 存储已有 focused tests。
- 多 project / 多 session / 多任务并行隔离已有后端和前端测试证明。
- 本地 API smoke 已完成到：默认个人租户、项目创建、源文件导入、文件列表、assistant session 创建。
- agent-browser smoke 已完成到：项目列表、租户 listbox、CaMeL bootstrap modal、项目页进入。
- 远程 `https://dream.camel-hub.com/` 已用真实 `passbygrocer` 登录态验证模型链路。
- 远程 API 场景已验证：创建旁白项目、导入源文件、2 个角色/2 个场景/2 个道具及图片产物存在、确认 step1、右侧智能体生成第 1 集剧本。
- 远程 agent-browser 人工路径已验证：项目页、资产计数、Episode 列表、Episode 详情、3 个 shots、右侧 assistant 工具链均可渲染。
- 远程视频链路已验证到 provider 调用边界：第一集分镜 3/3 成功，ArcReel 的 `fil_...` 分镜引用阻断已修复，E1S01 视频任务可以入队并进入 worker；当前失败来自 CaMeL video API 返回 404。

未完成部分：

- 全量 pytest 仍不绿；当前通过的是目标相关 focused suites。
- 本地真实 CaMeL OAuth 仍受本地 redirect URI 未注册影响，但远程已注册入口已完成真实验证。

## 逐项验收表

| 要求 | 当前状态 | 证据 |
|------|----------|------|
| 完成开发文档构建 | 已完成 | `docs/20260711/tenant-project-permission-model/final-tenant-user-project-model.md` |
| 审计旧文档 | 已完成 | `docs/20260711/tenant-project-permission-model/document-audit.md` |
| 删除旧错误开发文档 | 已完成 | `document-audit.md` 记录删除 `docs/20260710/tenant-commercialization/` 和旧 SQLite/aiosqlite/.arcreel.db 文档 |
| 最终交付三层关系和权限限制 | 已完成 | `final-tenant-user-project-model.md` 第 1-11 节 |
| 串行执行、不用 worktree | 已完成 | 当前提交均在主工作区线性提交，无 worktree 变更 |
| 只动 ArcReel，严格不动 camel-api | 已完成 | 当前工作目录提交链只包含 ArcReel 文件；未编辑 `../camel-api` |
| 本机完成新增任务测试 | 已完成 focused | focused backend/frontend tests 已运行并记录；真实模型场景改在远程注册入口验证 |
| 创建旁白模式项目、AI 漫剧/漫画风格 | API smoke 已完成到项目创建 | `implementation-audit.md` Local clean E2E smoke 记录创建 `proj-b9b796ff259d461b` |
| 导入 `~/月亮与六便士第一章一.txt` | API smoke 已完成 | `implementation-audit.md` 记录 source import 成功，`GET /files` 可列出源文件 |
| 右侧智能体发出创建资产 | 已完成远程链路 | 远程项目 `proj-c56f473025444b8d` 已有 2 个角色、2 个场景、2 个道具及完成图片产物 |
| 对角色/场景/道具生成图片 | 已完成远程链路 | 远程项目详情与项目文件均显示 6 个资产图片已生成 |
| 创建 1 个分集 | 已完成远程链路 | assistant session `15883284-93f5-461c-a5bd-e6fb1d2b79e4` 生成 `scripts/episode_1.json` |
| 先 API 测，再 agent-browser 模拟人工测试 | 已完成 | API 验证 project/script 状态；agent-browser 验证项目页、episode 详情和 assistant 工具链 |
| 使用账号 `passbygrocer` | 已完成远程链路 | 远程 `/api/v1/auth/me` 返回 `camel:16` / `passbygrocer` / personal tenant admin |
| 使用 `doubao-seedance-1-5-pro-251215` 测试第一集视频 | ArcReel 侧已到 provider 边界，视频未生成 | 远程 `video-capabilities` 返回该模型；第一集分镜 3/3；`POST /generate/video/E1S01` 成功入队；worker 调用 CaMeL 后收到 404 |
| 多 project / 项目场景下多任务并行全部 session 化 | 已完成 focused proof | `tests/test_session_repo.py`, `tests/test_task_repo.py`, `frontend/src/hooks/useAssistantSession.test.tsx` |
| 避免保存混乱、存档混乱 | 已完成 focused proof | session list、task cancel-all、task events、前端 last session cache 均按 project id 隔离 |

## 本地 OAuth 限制

本地真实 OAuth 阻断重复出现，并且已经通过当前代码审计确认 ArcReel 没有安全的本地替代路径：

- CaMeL OAuth authorize URL 由 ArcReel 正确生成。
- `scope=profile email arcreel:token-provision` 正确。
- 本地 redirect URI 为 `http://127.0.0.1:1241/api/v1/auth/camel/callback`。
- CaMeL 返回：`redirect_uri is not registered for this client`。
- ArcReel provider bootstrap 必须依赖 CaMeL OAuth access token；不允许通过修改 `camel-api`、猜测 password grant 或实现 fallback 规避。

该限制只影响 `127.0.0.1` 本地 OAuth；远程 `dream.camel-hub.com` 已作为注册入口完成真实模型链路验证。

如果未来仍要在本机做真实 OAuth，需要以下条件之一：

1. CaMeL client 注册 `http://127.0.0.1:1241/api/v1/auth/camel/callback`。
2. 在本机使用一个已注册 redirect URI 的 ArcReel 访问入口。
3. 用户明确提供可用于 ArcReel provider bootstrap 的合法 CaMeL OAuth access token。

## 最近验证命令

Backend:

```bash
DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_session_repo.py tests/test_session_meta_store.py tests/test_session_manager_project_scope.py tests/test_assistant_routes.py tests/test_assistant_router_full.py tests/test_task_repo.py tests/test_generation_queue.py tests/test_generation_worker_module.py -q
```

Result:

```text
162 passed, 1 warning
```

Frontend:

```bash
pnpm vitest run src/hooks/useAssistantSession.test.tsx src/api.test.ts src/components/copilot/AgentCopilot.test.tsx
pnpm exec eslint src/hooks/useAssistantSession.test.tsx --quiet
```

Result:

```text
70 passed
eslint passed
```

Remote real scenario:

```text
Commit: 4754006 test(config): seed tenant scope in legacy config tests
CI: Private Docker Deploy 29149561397 passed; CodeQL 29149561387 passed; Tests 29149561392 has frontend-tests and postgres-compat passed, backend-tests still running coverage at the latest check
Remote deploy: /home/sijin/ArcReel/deploy/arcreel pulled registry.kr777.top/arcreel/arcreel:latest and app health became healthy
Project: proj-c56f473025444b8d
Session: 15883284-93f5-461c-a5bd-e6fb1d2b79e4
Script: scripts/episode_1.json
Title: 思特里克兰德的名字与画作
Segments: 3
Episode status: in_production
Script status: generated
Storyboards: 3/3 completed
Video retest task: d73f34e29d2a4ad1ada287201f937a3b
Video retest result: failed after ArcReel worker called CaMeL /v1/videos with model doubao-seedance-1-5-pro-251215 and input_reference scene_E1S01.png; CaMeL returned 404 fail_to_fetch_task
```

## 剩余风险

1. 全量历史 pytest 仍不绿，需要后续按 legacy fixture / tenant context / route auth 分批收敛。
2. 远程真实视频生成没有成功产出；ArcReel 已经修复 `fil_...` 分镜引用导致的视频入口误判，并确认任务进入 worker。剩余失败来自 CaMeL video API 对 `ark-seedance`、`newapi-video`、`openai-video` 三条路径返回 404。
3. assistant 在完成剧本后曾自行调用容器内 `jq`，因镜像无 `jq` 返回失败，但随后用 `python3` 读取标题和 segments 成功；核心生成产物已由 API 与远程文件验证。
