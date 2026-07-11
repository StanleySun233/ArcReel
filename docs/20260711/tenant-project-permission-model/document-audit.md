# 租户权限开发文档审计

**日期:** 20260711
**状态:** current

## 权威文档

当前三层权限模型只以本目录下文档为准：

- [final-tenant-user-project-model.md](./final-tenant-user-project-model.md)
- [permission-model-design.md](./permission-model-design.md)
- [api-contract.md](./api-contract.md)
- [sprint-backlog.md](./sprint-backlog.md)

`docs/superpowers/` 下的历史 plans/specs 是过往实现记录，不作为当前商业发行版的权限、存储、数据库或部署契约来源。

## 已删除旧文档

已删除 `docs/20260710/tenant-commercialization/`，并从 `docs/INDEX.md` 移除该条目。

已删除 `docs/superpowers/plans/` 和 `docs/superpowers/specs/` 下仍记录 SQLite / aiosqlite / `.arcreel.db` / SQLite migration 的历史开发文档。

删除原因：

- 旧文档将项目 API 和文件路径绑定到 `project_name`。
- 旧文档记录了 Issued Tokens / external access tokens 作为已实现能力。
- 旧文档使用 story/worktree 并行计划。
- 旧文档包含旧兼容和历史修复记录，和当前“新发行版、不做旧兼容”的口径冲突。
- 旧文档继续传播 SQLite、本地 `.arcreel.db`、旧数据迁移脚本、SQLite/PG 双栈测试矩阵等已经废弃的数据库方案。

## 最终口径

| 主题 | 当前结论 |
|------|----------|
| 层级关系 | User 通过 membership 进入 Tenant，Tenant 拥有 Project |
| 项目归属 | 一个 Project 只属于一个 Tenant |
| 项目查询键 | 所有业务查询走 `project_id` |
| 项目名称 | `name` 只展示，租户内唯一，跨租户可重复 |
| 项目路径 | `_tenants/{tenant_id}/projects/{project_id}/project.json` |
| 权限来源 | 后端查询 membership，不相信前端 role/tenant_id |
| JWT role | 只做 UI 展示和 stale refresh |
| Issued Tokens | 后台统一 `403 feature_disabled`，前端按钮 disabled；不影响 CaMeL provider keys、媒体供应商凭证、Agent 凭证 |
| 成员查询 | viewer 允许查询成员列表 |
| 项目删除 | 仅 owner/admin |
| 执行方式 | 串行执行，不拆 story，不使用 worktree 并行 |

## 当前检查结果

- `docs/INDEX.md` 只保留当前 `tenant-project-permission-model` 活跃入口。
- `docs/20260710/tenant-commercialization/` 已无跟踪文件。
- 当前权威文档明确不保留旧项目名路径、不做旧版 project.json 兼容。
- 当前权威文档明确 Issued Tokens disable 行为。
- 当前权威文档明确串行执行方式。
- 已新增最终交付文档，集中描述租户、用户、项目三层关系、权限矩阵、文件、配置、任务、Agent 和用量边界。
- `docs/20260710/tenant-commercialization/` 目录已从工作树清除。
- 除本审计记录外，`docs/` 下已无 SQLite / aiosqlite / `.arcreel.db` / `migrate_sqlite_to_orm` 文档命中。
