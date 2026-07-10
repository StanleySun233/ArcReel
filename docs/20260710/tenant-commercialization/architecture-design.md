# ArcReel Tenant Commercialization Architecture Design

**Date:** 20260710
**Status:** draft
**Scope:** 新发行版商业化租户系统、PostgreSQL RLS、Redis 权限缓存、MinIO 私有文件存储、租户化项目/资产/配置/任务。

## 1. Product Decisions

这个设计按独立新发行版处理，不保留 SQLite、本地媒体路径、旧 `project.json` 媒体字段、旧 `_users/{user_id}` 目录、旧全局资产库的运行时兼容分支。

已确认的产品规则：

- CaMeL 只负责账号授权登录，ArcReel 负责租户、成员、权限和业务数据归属。
- 首次 CaMeL 登录后，如果用户没有任何 ArcReel 租户，ArcReel 自动创建个人空间，名称为 `{user_name}的个人空间`。
- 用户可加入多个租户，登录默认进入个人空间。进入其他租户必须通过前端 listbox 手动切换。
- 业务请求只携带当前租户 access token。前端缓存 `tenant_role` 只用于 UI 展示。
- 后端解析 JWT 得到 `user_id`、`tenant_id`、UI role snapshot，但真实权限一律查 Redis/PG。
- 角色只有 `admin`、`member`、`view`。租户所有者通过 `tenants.owner_user_id` 表示，不作为第四种 role。
- owner 默认是个人空间创建者。第一版不做 owner 转让 API，但模型预留。
- owner 必须保持 `admin` membership，不能被移出或降级。
- owner 可添加或提升 `admin`。普通 `admin` 可添加 `member` 和 `view`。`member` 可添加 `view`。`view` 只读。
- 只允许添加已经在 ArcReel 激活过的用户，不做 ArcReel 内部注册、密码、邮箱邀请或外部账号业务。
- 所有业务数据按 `tenant_id` 归属：项目、任务、usage/cost、API key、供应商配置、Agent 配置、租户资产库。
- 个人资产库按 `user_id` 归属，租户资产库按 `tenant_id` 归属。资产实体与库条目用 binding 多对多绑定。
- 资产跨库导入创建快照资产，binding 记录 `parent_binding_id`。同步只做手动拉取，覆盖前端需确认。
- 已提交生成任务只在发起请求时校验权限。用户后续被降级或移除，不取消已入队或运行中任务。
- PostgreSQL 是唯一数据库后端。SQLite 完全退出开发、测试、生产路径。
- Redis 第一版只用于权限/成员缓存和 token refresh 辅助，不缓存文件元数据、签名 URL、租户列表。
- MinIO bucket 私有。前端访问文件必须通过 ArcReel 后端短签名 URL。后端内部服务直接通过 FileService 用 `file_id` 读写对象。
- 本地中间件使用 `deploy/dev/docker-compose.middleware.yml`，包含 PostgreSQL、Redis、固定 release 的 MinIO Console 版本。

## 2. Non-Goals

- 不兼容旧 SQLite 数据库。
- 不兼容旧本地媒体路径。
- 不保留 `project.json` 旧媒体字段运行时 fallback。
- 不把 `project.json` 的完整项目元数据迁入 PostgreSQL。
- 不做 owner 转让 UI/API。
- 不做租户邀请邮件、外部账号注册、密码登录、ArcReel 内账号生命周期管理。
- 不做自动资产同步。
- 不做计费、套餐、额度、审计报表。
- 不做多区域对象存储、CDN、分布式 MinIO 集群。

## 3. Target Architecture

目标形态：

```text
React SPA
  -> FastAPI /api/v1
    -> Auth/Tenant dependencies produce TenantContext(user_id, tenant_id)
    -> PermissionService checks Redis, falls back to PostgreSQL
    -> SQLAlchemy AsyncSession applies PostgreSQL app.current_user_id / app.current_tenant_id
    -> Repositories query tenant-owned rows with app-level tenant filters
    -> PostgreSQL RLS denies tenant-owned rows outside current tenant
    -> FileService stores file metadata in PostgreSQL and objects in private MinIO bucket
```

边界：

- JWT 是租户选择凭据，不是权限真相源。
- Redis 是权限缓存，不是权限真相源。
- PostgreSQL 是业务和权限真相源。
- MinIO 是文件对象存储，不承载业务权限。
- 本地文件系统只保存 tenant-scoped `project.json`，不保存媒体产物。

## 4. Database Baseline

`lib/db/engine.py` 改为 PostgreSQL only：

- `DATABASE_URL` 必填。
- 只接受 `postgresql+asyncpg://...`。
- 删除 SQLite default、SQLite pragma、SQLite 测试 fixture 依赖。
- 测试环境使用本地或 CI PostgreSQL。
- Alembic migration 只针对 PostgreSQL 编写，可以使用 PostgreSQL enum、uuid、partial index、RLS policy。

RLS 基础：

- 每个请求建立 `TenantContext`。
- DB session 在 transaction begin 时设置：
  - `app.current_user_id`
  - `app.current_tenant_id`
  - `app.auth_mode = tenant`
- worker 处理任务时从 task row 恢复 `tenant_id` 和 `requested_by_user_id`，设置同样 DB context。
- 没有 tenant context 时，租户业务表的 RLS 默认拒绝。

## 5. Tenant Domain

核心表：

```text
users
  id
  username
  provider
  provider_subject
  is_active
  camel_provider_bootstrap_completed_at

tenants
  id
  name
  owner_user_id
  personal_for_user_id nullable unique
  created_by_user_id
  created_at
  updated_at

tenant_memberships
  id
  tenant_id
  user_id
  role enum(admin, member, view)
  created_by_user_id
  created_at
  updated_at
  unique(tenant_id, user_id)
```

规则：

- `personal_for_user_id` 非空表示个人空间。
- 每个激活用户最多一个个人空间。
- `tenants.owner_user_id` 必须存在于 `tenant_memberships` 且 role 为 `admin`。
- 删除/降级 membership 时，如果 user 是 owner，拒绝。
- 创建租户时在同一事务里写 `tenants` 和 owner membership。
- 登录时默认签发个人空间 token。

## 6. Auth And Token Flow

CaMeL 登录回调：

1. ArcReel 用 CaMeL userinfo upsert 本地 `users`。
2. 如果用户没有个人空间，创建 personal tenant 和 owner membership。
3. 默认选择 personal tenant。
4. 查询真实 membership。
5. 签发 tenant-scoped ArcReel JWT。

JWT payload：

```json
{
  "sub": "display_name_or_provider_subject",
  "user_id": "usr_...",
  "tenant_id": "ten_...",
  "tenant_role": "admin",
  "provider": "camel",
  "iat": 0,
  "exp": 0
}
```

授权：

- 后端解析 JWT 得到 `user_id` 和当前 `tenant_id`。
- 后端用 `PermissionService` 查 `user_id + tenant_id` 当前 membership 和 owner 状态。
- JWT `tenant_role` 只给前端展示。
- membership 变更后 Redis cache 失效，下一次业务请求立即按新权限判断。
- 前端遇到权限相关 403 时调用 refresh 接口重新签发当前租户 JWT；如果用户已无当前租户权限，回到个人空间。

## 7. Permission Cache

Redis key：

```text
tenant-permission:{user_id}:{tenant_id}
```

Value：

```json
{
  "role": "admin",
  "is_owner": true,
  "permissions_version": 12,
  "expires_at": "..."
}
```

策略：

- 读权限先查 Redis，miss 后查 PostgreSQL。
- membership/owner 变化时删除相关 key 或 bump version。
- Redis 不保存租户列表。
- Redis 不保存文件元数据。
- Redis 不保存 signed URL。

## 8. Role Permissions

`admin`：

- 项目、资产、生成、上传、配置、API key、供应商、Agent 配置全权限。
- 可添加 `member` 和 `view`。
- 如果同时是 owner，可添加/提升 `admin`。

`member`：

- 可创建、上传、编辑项目。
- 可发起生成任务。
- 可管理业务资产。
- 可把个人资产或可读租户资产导入当前租户。
- 可添加 `view`。
- 不可管理租户设置、删除租户、添加/提升 `admin`。

`view`：

- 可读项目、资产、任务状态、生成结果、配置展示。
- 不可写项目、上传、生成、修改资产、修改配置、管理成员。

## 9. PostgreSQL RLS

启用 RLS 的租户业务表：

- `projects`
- `tasks`
- `task_events`
- `api_calls`
- `api_keys`
- `provider_config`
- `system_setting`
- `provider_credential`
- `custom_providers`
- `custom_provider_models`
- `agent_anthropic_credentials`
- `tenant_asset_bindings`
- `usage/cost` 相关表

典型 policy：

```sql
USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
```

特殊表：

- `users`：不按租户 RLS。服务层只允许查激活用户和当前用户需要的最小字段。
- `tenants`：允许当前用户通过 membership 读取可进入租户；写入走 service 权限。
- `tenant_memberships`：允许当前用户读取自己的 memberships；当前 tenant 的 admin/member 管理接口通过 service 权限控制。
- `files`：全局文件对象，不放单一 `tenant_id`，不直接靠 RLS 判业务可见性。
- `file_links`：作为访问索引和 GC 辅助，可带 `tenant_id` 或 `user_id`，但不是最终权限真相源。

RLS 不是唯一防线。所有 repository/service 仍必须显式接受 `TenantContext` 或由请求依赖注入当前 tenant session。

## 10. Files And MinIO

核心表：

```text
files
  id
  object_key
  ext
  alias
  mime_type
  size_bytes
  sha256
  created_by_user_id
  created_at
  deleted_at nullable

file_links
  id
  file_id
  link_type
  tenant_id nullable
  user_id nullable
  project_id nullable
  asset_binding_id nullable
  purpose
  created_at
```

MinIO：

- bucket 私有。
- object key 使用 `{uuid}.{ext}` 格式，不使用真实文件名。
- `alias` 保存真实/显示文件名。
- `files.id` 是业务引用 ID。
- `project.json`、资产表、任务结果只保存 `file_id`。
- 前端调用 `GET /api/v1/files/{file_id}/signed-url` 获取短期 URL。
- 后端内部调用 FileService 读取对象，不走 signed URL。
- 删除业务引用不立即删 MinIO object。GC 只清理没有任何引用的 file。

## 11. Project System

第一版不迁移项目内容模型到 PostgreSQL，但新增 `projects` registry 表：

```text
projects
  id
  tenant_id
  name
  content_mode
  generation_mode
  created_by_user_id
  created_at
  updated_at
  unique(tenant_id, name)
```

本地项目路径：

```text
$ARCREEL_DATA_DIR/_tenants/{tenant_id}/projects/{project_name}/project.json
```

规则：

- `ProjectManager` 必须由 `TenantContext` 构造或显式接收 `tenant_id`。
- 不再存在全局 projects 目录作为业务读写入口。
- 不再存在 `_users/{user_id}` 项目作用域。
- `project.json` 媒体字段只保存 `file_id` 或包含 `file_id` 的结构。
- 不识别旧本地路径字段。
- 上传、生成、参考视频、字幕/文本产物进入 FileService/MinIO 后再写入 `project.json`。

## 12. Asset Library

资产实体：

```text
assets
  id
  type
  name
  description
  voice_style
  image_file_id nullable
  metadata_json
  created_by_user_id
  created_at
  updated_at
```

统一 binding：

```text
asset_library_bindings
  id
  asset_id
  library_type enum(user, tenant)
  user_id nullable
  tenant_id nullable
  parent_binding_id nullable
  created_by_user_id
  created_at
  updated_at
```

规则：

- `library_type=user` 时必须有 `user_id` 且 `tenant_id` 为空。
- `library_type=tenant` 时必须有 `tenant_id` 且 `user_id` 为空。
- 导入时创建新 asset row 和新 binding，`parent_binding_id` 指向来源 binding。
- 导入不会复制底层 file object，只复用 `file_id`。
- 手动 sync 从 parent binding 找来源 asset，将来源当前资产字段复制到目标 asset。
- sync 前后权限都要校验：目标库 `member+`，来源库可读。

## 13. Configuration And API Keys

这些表从 user-owned 改为 tenant-owned：

- `provider_config`
- `system_setting`
- `provider_credential`
- `custom_providers`
- `custom_provider_models`
- `agent_anthropic_credentials`
- `api_keys`

规则：

- 用户首次登录后的个人配置都落在个人空间 tenant。
- 租户切换后配置读取当前 tenant。
- API key tenant-scoped，包含 `tenant_id` 和创建用户。
- API key 请求解析出 key owner 后，仍需校验该用户在 key 所属 tenant 的当前 membership。用户被移出租户后，其 API key 不再可用。

## 14. Generation Tasks And Workers

`tasks` 增加：

```text
tenant_id
requested_by_user_id
```

规则：

- 入队时校验当前用户在当前租户是否有发起该任务的权限。
- 入队后 task 固化 `tenant_id` 和 `requested_by_user_id`。
- worker 执行时从 task 恢复 DB tenant context。
- 用户后续被降级或移除，不影响已提交任务继续执行。
- 任务查询、SSE、取消等业务请求仍按当前用户当前 tenant 权限判断。
- dedupe index 加入 `tenant_id`，避免不同租户同名项目互相影响。

## 15. Frontend UX

前端 auth store 保存：

- access token
- current tenant id
- current tenant name
- cached `tenant_role`
- is owner
- tenant list for listbox display

行为：

- 登录回调后默认进入个人空间。
- 顶部或设置入口提供租户 listbox。
- 切换租户调用 `POST /api/v1/auth/tenant-token`，成功后替换 token 并刷新租户态。
- `tenant_role` 控制按钮显隐，但后端 403 是最终裁决。
- 403 stale role 时刷新当前租户 token；失去租户权限时回个人空间。

## 16. API Surface

详细接口见 `api-contract.md`。关键点：

- 业务接口不接受前端传来的 role。
- 业务接口默认不接受 body/header tenant_id。
- 租户切换接口接受目标 `tenant_id`，但只用于后端查 membership 后重新签 token。
- 成员管理接口作用于当前 token 的 tenant。
- 文件签名接口只接受 `file_id`，权限由后端引用关系判断。

## 17. Migration Strategy For This New Edition

因为这是独立新发行版：

- 不提供旧版本运行时兼容。
- 不提供 SQLite fallback。
- 不提供旧本地路径 fallback。
- 允许提供一次性导入脚本，但导入失败的项目不能进入新版本。
- 项目导入完成后，`project.json` 内媒体引用必须全部是 `file_id`。

如果不做导入脚本，新发行版可从空库启动。

## 18. Development Environment

本地中间件：

- Compose file: `deploy/dev/docker-compose.middleware.yml`
- PostgreSQL: `127.0.0.1:15432`
- Redis: `127.0.0.1:16379`
- MinIO API: `127.0.0.1:19000`
- MinIO Console: `127.0.0.1:19001`
- Bucket: `arcreel-files`

MinIO 当前使用固定 release tag，不使用 `latest`。商业化前需要确认 MinIO 社区版 AGPLv3 义务和商业授权风险。

## 19. Testing Strategy

最低测试层级：

- DB/RLS：PostgreSQL 集成测试，验证缺失 tenant context 拒绝、跨租户查询拒绝、同租户通过。
- Auth：CaMeL 登录默认个人空间、多租户切换、JWT role stale refresh、被移出租户回退。
- Permission：owner/admin/member/view 的成员管理矩阵。
- File：上传入 MinIO、files 表写入、私有 bucket、signed URL、越权 file_id 拒绝、GC 引用计数。
- Project：tenant 目录、project registry、`project.json` file_id schema、跨租户同名项目隔离。
- Asset：个人库、租户库、快照导入、手动 sync、跨租户权限。
- Task：入队权限、task tenant context、worker 写回 file_id、降级后已提交任务继续。
- Frontend：租户 listbox、权限 UI、403 refresh、file_id 按需换签名 URL。

## 20. Main Risks

- RLS session context 如果漏设置，功能会被拒绝；如果错误设置，会产生严重隔离事故。需要集中封装并强制测试。
- `files` 是全局表，不能靠单一 `tenant_id` 判权。所有文件访问必须经过 FileService，不允许路由绕过。
- `project.json` 仍在本地文件系统，横向扩展需要共享盘或后续迁移项目元数据/对象到存储层。
- 资产 sync 会覆盖目标快照，需要前端确认和后端明确操作语义。
- 放弃 SQLite 会影响大量现有测试 fixture，需要作为独立故事处理。
- MinIO 社区版授权和商业使用风险需要在商业发布前确认。
