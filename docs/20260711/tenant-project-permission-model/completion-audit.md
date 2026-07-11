# Completion Audit: tenant/user/project goal

**Date:** 20260711  
**Status:** not complete  
**Scope:** 用户原始目标逐项审计。只以当前 ArcReel 工作树、测试输出、运行记录和文档为证据；不包含 `../camel-api`。

## 结论

当前目标不能标记完成。

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

未完成部分：

- 真实 CaMeL OAuth 登录在本地无法完成，因为 CaMeL 拒绝本地 redirect URI。
- 因真实 provider bootstrap 无法完成，无法在本机完成真实文本/图片模型生成链路。
- 因模型链路未完成，用户指定的完整场景不能被证明：右侧智能体创建 3 个角色、3 个场景、3 个道具，生成图片，再创建 1 个分集。
- 全量 pytest 仍不绿；当前通过的是目标相关 focused suites。

## 逐项验收表

| 要求 | 当前状态 | 证据 |
|------|----------|------|
| 完成开发文档构建 | 已完成 | `docs/20260711/tenant-project-permission-model/final-tenant-user-project-model.md` |
| 审计旧文档 | 已完成 | `docs/20260711/tenant-project-permission-model/document-audit.md` |
| 删除旧错误开发文档 | 已完成 | `document-audit.md` 记录删除 `docs/20260710/tenant-commercialization/` 和旧 SQLite/aiosqlite/.arcreel.db 文档 |
| 最终交付三层关系和权限限制 | 已完成 | `final-tenant-user-project-model.md` 第 1-11 节 |
| 串行执行、不用 worktree | 已完成 | 当前提交均在主工作区线性提交，无 worktree 变更 |
| 只动 ArcReel，严格不动 camel-api | 已完成 | 当前工作目录提交链只包含 ArcReel 文件；未编辑 `../camel-api` |
| 本机完成新增任务测试 | 部分完成 | focused backend/frontend tests 已运行并记录；真实模型场景受 OAuth 阻断 |
| 创建旁白模式项目、AI 漫剧/漫画风格 | API smoke 已完成到项目创建 | `implementation-audit.md` Local clean E2E smoke 记录创建 `proj-b9b796ff259d461b` |
| 导入 `~/月亮与六便士第一章一.txt` | API smoke 已完成 | `implementation-audit.md` 记录 source import 成功，`GET /files` 可列出源文件 |
| 右侧智能体发出创建 3 角色/3 场景/3 道具 | 未完成 | assistant session 创建可运行；真实 agent 执行返回 `Not logged in · Please run /login` |
| 对角色/场景/道具生成图片 | 未完成 | provider bootstrap 未完成，不能真实调用 image 模型 |
| 创建 1 个分集 | 未完成 | provider bootstrap/agent 登录阻断，未完成真实 agent scenario |
| 先 API 测，再 agent-browser 模拟人工测试 | 部分完成 | API smoke 和 browser smoke 已做；完整模型链路未做 |
| 使用账号 `passbygrocer` | 部分完成 | 本地用 `camel:passbygrocer` synthetic token 验证 ArcReel 内部；真实 CaMeL OAuth 未完成 |
| 不动视频 | 已遵守 | 本地测试未触发视频生成 |
| 多 project / 项目场景下多任务并行全部 session 化 | 已完成 focused proof | `tests/test_session_repo.py`, `tests/test_task_repo.py`, `frontend/src/hooks/useAssistantSession.test.tsx` |
| 避免保存混乱、存档混乱 | 已完成 focused proof | session list、task cancel-all、task events、前端 last session cache 均按 project id 隔离 |

## 阻断条件

本地真实 OAuth 阻断重复出现，并且已经通过当前代码审计确认 ArcReel 没有安全的本地替代路径：

- CaMeL OAuth authorize URL 由 ArcReel 正确生成。
- `scope=profile email arcreel:token-provision` 正确。
- 本地 redirect URI 为 `http://127.0.0.1:1241/api/v1/auth/camel/callback`。
- CaMeL 返回：`redirect_uri is not registered for this client`。
- ArcReel provider bootstrap 必须依赖 CaMeL OAuth access token；不允许通过修改 `camel-api`、猜测 password grant 或实现 fallback 规避。

因此，除非以下条件之一发生，否则本机无法继续完成真实模型链路：

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

## 下一步条件

如果 redirect URI 被注册或提供了合法 OAuth token，下一步应继续：

1. 清理 ArcReel 本地 PG/Redis。
2. 使用真实 CaMeL OAuth 登录 `passbygrocer`。
3. 完成 CaMeL provider bootstrap。
4. API 先跑完整场景：创建项目、导入源文件、创建角色/场景/道具、生成图片、创建分集。
5. agent-browser 再按人工路径复测。
6. 更新本文件和 `implementation-audit.md`，再判断目标是否完成。
