# 租户权限开发文档审计

**日期:** 20260711
**状态:** current

## 权威文档

当前三层权限模型只以本目录下文档为准：

- [permission-model-design.md](./permission-model-design.md)
- [api-contract.md](./api-contract.md)
- [sprint-backlog.md](./sprint-backlog.md)

`docs/superpowers/` 下的历史 plans/specs 是过往实现记录，不作为当前商业发行版的权限、存储、数据库或部署契约来源。

## 已删除旧文档

已删除 `docs/20260710/tenant-commercialization/`，并从 `docs/INDEX.md` 移除该条目。

删除原因：

- 旧文档将项目 API 和文件路径绑定到 `project_name`。
- 旧文档记录了 Issued Tokens / external access tokens 作为已实现能力。
- 旧文档使用 story/worktree 并行计划。
- 旧文档包含旧兼容和历史修复记录，和当前“新发行版、不做旧兼容”的口径冲突。

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
- `docs/20260710/tenant-commercialization/` 目录已从工作树清除。
