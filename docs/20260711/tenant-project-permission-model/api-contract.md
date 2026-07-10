# API Contract: Tenant Project Permission Model

**日期:** 20260711
**状态:** draft
**适用范围:** 新商业发行版；不兼容旧版项目名路由。

## 通用请求上下文

认证后端从 access token 解析：

- `user_id`
- `tenant_id`
- `tenant_role` 快照，仅用于 UI 刷新提示

业务接口不接受前端传入的 `tenant_id` 或 `role` 作为授权依据。后端从 token 的 `tenant_id` 得到当前租户，再查询真实 membership。

## 项目 API

所有项目 API 使用 `project_id`。

| 旧形态 | 新形态 | 说明 |
|--------|--------|------|
| `GET /api/v1/projects/{name}` | `GET /api/v1/projects/{project_id}` | `name` 只在响应里展示 |
| `PATCH /api/v1/projects/{name}` | `PATCH /api/v1/projects/{project_id}` | 校验当前租户内 `name` 不重复 |
| `DELETE /api/v1/projects/{name}` | `DELETE /api/v1/projects/{project_id}` | 仅 owner/admin 允许 |
| `POST /api/v1/projects/{name}/generate-overview` | `POST /api/v1/projects/{project_id}/generate-overview` | 使用 ProjectContext |
| `GET /api/v1/projects/{name}/events/stream` | `GET /api/v1/projects/{project_id}/events/stream` | SSE channel 使用 project_id |
| `POST /api/v1/projects/{name}/assistant/sessions/send` | `POST /api/v1/projects/{project_id}/assistant/sessions/send` | Agent cwd 使用 project_id |

项目响应字段：

```json
{
  "id": "proj_xxx",
  "tenant_id": "tenant_xxx",
  "name": "显示名称",
  "created_by_user_id": "user_xxx",
  "updated_at": "2026-07-11T00:00:00Z"
}
```

前端必须把 `id` 作为路由、缓存、SSE、任务过滤、localStorage 的唯一项目键。

## 租户 API

| Endpoint | 权限 | 说明 |
|----------|------|------|
| `GET /api/v1/auth/me` | 登录用户 | 返回当前用户、当前租户、role 快照 |
| `GET /api/v1/auth/tenants` | 登录用户 | 返回用户 membership 列表 |
| `POST /api/v1/auth/tenant-token` | 登录用户 + 目标租户 membership | 切换当前租户，返回新 access token |
| `POST /api/v1/auth/refresh-current-tenant` | 登录用户 + 当前租户 membership | role 快照过期后刷新 token |
| `GET /api/v1/tenants/{tenant_id}/members` | admin/member/view | viewer 允许查询成员列表 |
| `POST /api/v1/tenants/{tenant_id}/members` | admin/member | admin 可加 member/view；member 只可加 view |
| `PATCH /api/v1/tenants/{tenant_id}/members/{user_id}` | owner/admin | owner 可加 admin；admin 不可提升 owner |
| `DELETE /api/v1/tenants/{tenant_id}/members/{user_id}` | owner/admin | 不允许删除最后 owner 预留规则 |

成员添加只允许选择 ArcReel 已激活用户。ArcReel 不做账号注册、密码、邮件验证业务；账号生命周期由 CaMeL 负责。

## 文件 API

| Endpoint | 权限 | 说明 |
|----------|------|------|
| `POST /api/v1/files` | member/admin | 上传后写 `files` 和 `file_links` |
| `GET /api/v1/files/{file_id}/signed-url` | 当前租户可访问该 file_link | 返回短签名 URL |
| `GET /api/v1/projects/{project_id}/files` | view/member/admin | 列出项目绑定文件 |

文件响应只返回：

- `file_id`
- `alias`
- `mime_type`
- `size`
- `signed_url` 在需要前端访问时短期返回

不返回 MinIO bucket、object key、服务器本地路径。

## 生成任务 API

所有生成入口路径必须包含 `project_id`，或 body 中只能包含 `resource_id/file_id`，项目上下文从 route resolver 得到。

任务入队记录：

```json
{
  "tenant_id": "tenant_xxx",
  "project_id": "proj_xxx",
  "requested_by_user_id": "user_xxx",
  "task_type": "video",
  "media_type": "video"
}
```

入队时检查当前用户权限。worker 执行时使用任务中持久化的 `tenant_id/project_id/requested_by_user_id`，不重新读取用户当前 token。

## 用量 API

| Endpoint | 权限 | 说明 |
|----------|------|------|
| `GET /api/v1/usage/tenant` | admin/member/view | 当前租户用量总览，按权限裁剪 |
| `GET /api/v1/usage/projects/{project_id}` | view/member/admin | 当前项目用量 |
| `GET /api/v1/usage/users/{user_id}` | admin 或本人 | 用户维度用量 |

查询参数：

- `from`
- `to`
- `project_id`
- `user_id`
- `provider_id`
- `model`
- `media_type`
- `group_by`

允许的 `group_by`：

- `project`
- `user`
- `provider`
- `model`
- `media_type`
- `day`

返回聚合项必须包含对应 ID；name 只作为 display 字段。

## Issued Tokens 禁用契约

本轮后台 Issued Tokens 功能默认不可用。这里指设置页里“API 密钥管理 / Issued Tokens”，用于 OpenClaw 等外部工具访问 ArcReel 项目；不包括 CaMeL provider provisioning keys、媒体供应商凭证、Anthropic Bridge / Agent 凭证。

| Endpoint | 行为 |
|----------|------|
| `GET /api/v1/api-keys` | 返回 `403 feature_disabled` |
| `POST /api/v1/api-keys` | 返回 `403 feature_disabled` |
| `PATCH /api/v1/api-keys/{id}` | 返回 `403 feature_disabled` |
| `DELETE /api/v1/api-keys/{id}` | 返回 `403 feature_disabled` |

前端 Issued Tokens 按钮保留但 disabled，不允许触发创建/更新/删除请求。测试必须覆盖按钮 disabled 和后台接口统一 403。

## 错误码

| 场景 | HTTP | code |
|------|------|------|
| 未登录 | 401 | `auth_required` |
| token 中无当前 tenant | 401 | `tenant_required` |
| 无 tenant membership | 403 | `tenant_access_denied` |
| role 快照过期 | 403 | `tenant_role_stale` |
| 项目不存在或不属于当前租户 | 404 | `project_not_found` |
| 权限不足 | 403 | `permission_denied` |
| Issued Tokens 功能关闭 | 403 | `feature_disabled` |
