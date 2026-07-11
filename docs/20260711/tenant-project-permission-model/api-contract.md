# API Contract: Tenant Project Permission Model

**日期:** 20260711
**状态:** accepted
**适用范围:** 新商业发行版；不保留旧版项目名路由。

## 通用请求上下文

认证后端从 access token 解析：

- `user_id`
- `tenant_id`
- `tenant_role` 快照，仅用于 UI 刷新提示

业务接口不接受前端传入的 `tenant_id` 或 `role` 作为授权依据。后端从 token 的 `tenant_id` 得到当前租户，再查询真实 membership。

## 项目 API

所有项目 API 使用 `project_id`。项目显示名只出现在响应和重命名 payload 中，不作为路由键、缓存键或业务查询键。

| Endpoint | 权限 | 说明 |
|----------|------|------|
| `GET /api/v1/projects` | view/member/admin | 当前租户项目列表 |
| `POST /api/v1/projects` | member/admin | 当前租户内创建项目，返回 `id` 和显示名 |
| `GET /api/v1/projects/{project_id}` | view/member/admin | 项目详情 |
| `PATCH /api/v1/projects/{project_id}` | admin/owner | 更新项目显示名或项目元数据；`project_id` 不可改 |
| `DELETE /api/v1/projects/{project_id}` | admin/owner | 删除项目目录和项目行 |
| `GET /api/v1/projects/{project_id}/video-capabilities` | view/member/admin | 视频模型能力解析 |
| `GET /api/v1/projects/{project_id}/cost-estimate` | view/member/admin | 项目费用估算 |
| `POST /api/v1/projects/{project_id}/generate-overview` | member/admin | 生成项目概述 |
| `GET /api/v1/projects/{project_id}/scripts/{script_file}` | view/member/admin | 读取剧本内容 |
| `PATCH /api/v1/projects/{project_id}/script-scenes/{scene_id}` | member/admin | drama 场景编辑 |
| `PATCH /api/v1/projects/{project_id}/script-shots/{shot_id}` | member/admin | 分镜编辑 |
| `PATCH /api/v1/projects/{project_id}/segments/{segment_id}` | member/admin | narration 片段编辑 |
| `PATCH /api/v1/projects/{project_id}/episodes/{episode}` | member/admin | 分集标题编辑 |
| `GET /api/v1/projects/{project_id}/episodes/{episode}/script-review` | view/member/admin | step1 审核读取 |
| `PUT /api/v1/projects/{project_id}/episodes/{episode}/script-review/content` | member/admin | step1 审核内容保存 |
| `POST /api/v1/projects/{project_id}/episodes/{episode}/script-review/confirm` | member/admin | step1 审核确认 |
| `POST /api/v1/projects/{project_id}/source` | member/admin | 源文件或源文本导入 |
| `GET /api/v1/projects/{project_id}/events/stream` | view/member/admin | 项目事件 SSE channel |
| `POST /api/v1/projects/{project_id}/assistant/sessions/send` | member/admin | Agent 消息发送和会话创建 |
| `GET /api/v1/projects/{project_id}/versions/{resource_type}/{resource_id}` | view/member/admin | 资源版本读取 |
| `POST /api/v1/projects/{project_id}/versions/{resource_type}/{resource_id}/restore/{version}` | member/admin | 版本还原 |
| `POST /api/v1/projects/{project_id}/generate/grid/{episode}` | member/admin | 宫格图生成 |
| `GET /api/v1/projects/{project_id}/grids` | view/member/admin | 宫格图列表 |
| `GET /api/v1/projects/{project_id}/grids/{grid_id}` | view/member/admin | 宫格图详情 |
| `POST /api/v1/projects/{project_id}/grids/{grid_id}/regenerate` | member/admin | 宫格图重生成 |
| `GET /api/v1/projects/{project_id}/reference-videos/episodes/{episode}/units` | view/member/admin | 参考视频单元列表 |
| `POST /api/v1/projects/{project_id}/reference-videos/episodes/{episode}/derive-units` | member/admin | ad 参考视频单元派生 |
| `POST /api/v1/projects/{project_id}/reference-videos/episodes/{episode}/units` | member/admin | 新增参考视频单元 |
| `PATCH /api/v1/projects/{project_id}/reference-videos/episodes/{episode}/units/{unit_id}` | member/admin | 编辑参考视频单元 |
| `DELETE /api/v1/projects/{project_id}/reference-videos/episodes/{episode}/units/{unit_id}` | member/admin | 删除参考视频单元 |
| `POST /api/v1/projects/{project_id}/reference-videos/episodes/{episode}/units/reorder` | member/admin | 重排参考视频单元 |
| `POST /api/v1/projects/{project_id}/reference-videos/episodes/{episode}/units/{unit_id}/generate` | member/admin | 参考视频单元生成 |
| `POST /api/v1/projects/{project_id}/reference-videos/episodes/{episode}/units/{unit_id}/upload-video` | member/admin | 手动上传参考单元视频 |
| `POST /api/v1/projects/{project_id}/export/token` | view/member/admin | 导出 token 签发 |
| `GET /api/v1/projects/{project_id}/export` | token | 下载 token 绑定 `tenant_id:project_id` |
| `GET /api/v1/projects/{project_id}/export/jianying-draft` | token | 剪映草稿导出 |
| `POST /api/v1/agent/chat` | disabled | OpenClaw 同步 Agent 入口返回 `403 feature_disabled` |

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
| `GET /api/v1/projects/{project_id}/drafts` | view/member/admin | 列出项目草稿 |
| `GET /api/v1/projects/{project_id}/drafts/{episode}/step{step}` | view/member/admin | 读取项目草稿 |
| `PUT /api/v1/projects/{project_id}/drafts/{episode}/step{step}` | member/admin | 写入项目草稿 |
| `DELETE /api/v1/projects/{project_id}/drafts/{episode}/step{step}` | member/admin | 删除项目草稿 |
| `POST /api/v1/projects/{project_id}/style-image` | member/admin | 上传项目风格参考图 |
| `POST /api/v1/projects/{project_id}/shots/{shot_id}/upload/{kind}` | member/admin | 手动上传镜头分镜图或视频，返回 file_id |

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
| `GET /api/v1/usage/stats?project_id={project_id}` | view/member/admin | 当前租户下的聚合统计 |
| `GET /api/v1/usage/calls?project_id={project_id}` | view/member/admin | 当前租户下的调用明细 |
| `GET /api/v1/usage/projects` | view/member/admin | 当前租户下有用量记录的项目 id 列表 |

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

`POST /api/v1/agent/chat` 属于 OpenClaw 等外部工具同步访问 ArcReel 项目的入口。本轮同 Issued Tokens 一起暂停：后台保留业务实现，入口默认返回 `403 feature_disabled`，不得绕过 tenant/project_id 权限模型。

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
