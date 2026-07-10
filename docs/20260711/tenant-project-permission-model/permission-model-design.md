# 租户、用户、项目权限关系设计

**日期:** 20260711
**状态:** draft
**适用范围:** ArcReel 新商业发行版。明确不做旧版本项目、SQLite、本地媒体路径、按项目名寻址的兼容。

## 目标

把 ArcReel 的业务边界收敛到三个稳定 ID：

```text
User <-- membership --> Tenant <-- owns --> Project
```

- `user_id` 表示 ArcReel 内部用户，身份来源由 CaMeL 授权登录导入。
- `tenant_id` 表示系统配置、权限、资产库、用量、项目归属边界。
- `project_id` 表示项目唯一业务键；所有业务逻辑按 `project_id` 查询。

`project.name` 只用于显示和租户内重名校验，不允许作为读取、写入、任务、Agent、文件、用量统计的业务查询键。

## 不变量

1. 一个项目只属于一个租户：`projects.tenant_id` 不可为空，不可变更到其他租户。
2. 用户和租户是多对多：用户通过 `tenant_memberships` 进入租户。
3. 用户和项目没有直接授权表；用户能否访问项目由当前租户成员身份决定。
4. 项目名称只在租户内唯一：`unique(tenant_id, name)`。
5. 所有项目查询必须使用 `project_id`，并强制附带当前后端解析出的 `tenant_id`。
6. 所有写操作权限由后端实时查询真实 membership 得到，不相信前端 JWT 里的 role。
7. JWT 中的 `tenant_role` 只作为 UI 快照。请求实际授权路径是 `user_id + tenant_id -> membership -> permission`。
8. 已提交任务不随 membership 后续变化中断；权限只在用户发出请求、入队、创建会话时检查。
9. API key 功能本轮下掉：后台路由、前端入口、创建/展示动作默认 disabled。后续再以 feature flag 或显式配置启用。
10. 文件存储统一使用 `file_id`，对象存储 key 使用 UUID 样式，真实文件名保存在 `alias`。

## 角色模型

| Role | 可做动作 | 不可做动作 |
|------|----------|------------|
| owner | 租户所有者；可添加 admin/member/viewer，可转移或预留转移设计 | 不直接参与项目业务查询键 |
| admin | 编辑租户配置、创建/编辑项目、添加 member/viewer | 不能添加 owner；是否能添加 admin 预留 owner 策略 |
| member | 创建项目、上传/生成视频、导入资产、添加 viewer | 不能编辑租户高级配置，不能添加 member/admin |
| view | 查看项目、查看资产、查看用量中自己被允许看到的范围 | 不能创建、上传、生成、编辑、导入 |

第一版落地角色枚举只保留 `admin/member/view`。`owner_user_id` 是租户字段，owner 默认拥有 admin 行为，并额外拥有添加 admin 的能力。owner 转移暂不实现，但表结构和服务接口不得卡死。

## 权限判定流程

```text
请求进入
  -> 解析 access token 得到 user_id + tenant_id + role_snapshot
  -> 后端按 user_id + tenant_id 查询 membership
  -> role_snapshot 只用于判断是否需要刷新 UI token，不用于授权
  -> ProjectContextResolver 用 tenant_id + project_id 查询项目
  -> PermissionService 判断 action 是否允许
  -> 业务 service 执行，所有 SQL 和文件路径继续携带 tenant_id + project_id
```

错误语义：

- 当前用户没有租户 membership：`403`。
- 项目不属于当前租户或不存在：对普通业务读写返回 `404`，避免跨租户枚举。
- membership 存在但权限不足：`403`。
- 前端 role 快照过期：后端返回可识别错误码，前端刷新当前租户 JWT 后重试用户主动发出的动作。

## ProjectContextResolver

需要新增或收敛一个统一入口，禁止各路由、worker、Agent 自己拼路径或按 name 加载项目。

输入：

- `tenant_id`
- `project_id`
- `user_id`
- `required_action`

输出：

- `tenant_id`
- `project_id`
- `project_name`
- `project_root`
- `project_json_path`
- `membership_role`
- `owner_user_id`

路径规则：

```text
$ARCREEL_DATA_DIR/_tenants/{tenant_id}/projects/{project_id}/project.json
```

不保留 `_users` 项目路径，不保留 `{project_name}` 项目路径，不做旧路径 fallback。

## 数据模型

核心表：

| 表 | 关键字段 | 规则 |
|----|----------|------|
| users | id, camel_user_id, username, display_name | CaMeL 身份映射；不使用 display name 做授权键 |
| tenants | id, name, owner_user_id, created_by_user_id | 个人空间默认名称 `{user_name}的个人空间` |
| tenant_memberships | tenant_id, user_id, role | `unique(tenant_id, user_id)` |
| projects | id, tenant_id, name, created_by_user_id | `unique(tenant_id, name)`；业务查找走 id |
| configs / credentials / custom_providers | tenant_id, scope | 系统配置归租户 |
| tasks | tenant_id, project_id, requested_by_user_id | worker 不重新查当前 membership |
| api_calls | tenant_id, project_id, user_id, task_id | 支持租户/项目/用户聚合 |
| files | id, object_key, alias, mime_type, size | 全局文件元数据，不直接公开 object_key |
| file_links | file_id, tenant_id, project_id, entity_type, entity_id | 文件和项目/资产/任务绑定 |
| assets | tenant_id, owner_user_id nullable, asset_type, data | 租户库和个人库通过字段区分 |
| asset_library_bindings | tenant_id, asset_id, parent_id, snapshot_data | 支持跨租户/个人导入、快照、手动 sync |
| agent_sessions | tenant_id, project_id, user_id | Agent 会话不得脱离项目上下文 |

本发行版不做旧数据迁移兼容。Alembic 可以直接表达新表结构，但不需要写旧 SQLite 或旧 project.json 转换逻辑。

## API key 暂停策略

当前阶段不实现用户级 API token 授权链路，原因是它会引入第四类授权入口，且现在主线目标是先把 `user/tenant/project` 三元模型收敛。

本轮要求：

- 后台不提供可用的 API key 创建、更新、删除、展示密钥接口。
- 前端设置页隐藏 API key 入口。
- 现有 API key 路由如果保留代码，默认返回 `404` 或 `403 feature_disabled`，不得参与真实鉴权。
- 测试覆盖“API key 功能关闭时不能创建 key，UI 不出现入口”。

后续启用预留：

- API key 属于创建它的 `user_id`。
- API key 权限来自创建者可见的 tenant/project 范围快照或显式 allowlist。
- API key 不允许跨越创建者没有 membership 的 tenant。
- API key 访问项目仍必须走 `tenant_id + project_id`。

## 用量统计

用量记录以 `api_calls` 为事实表，至少保留：

- `tenant_id`
- `project_id nullable`
- `user_id`
- `task_id nullable`
- `provider_id`
- `model`
- `media_type`
- `operation`
- `input_units`
- `output_units`
- `cost`
- `status`
- `created_at`

展示维度：

- 租户总览：按项目、用户、provider、model、media_type 分组。
- 项目详情：按用户、任务、provider、model、media_type 分组。
- 用户视角：只显示自己有权进入的 tenant/project。

禁止按项目名聚合；项目名只作为 join 后的展示字段。

## Agent 和任务链路

Agent 会话创建、消息发送、工具调用、任务入队必须携带同一个 `ProjectContext`。

关键规则：

- `/assistant/sessions/send` 路由参数使用 `project_id`。
- Agent cwd 由 `project_id` 路径计算。
- MCP 工具不接受或推断项目名；只接收上下文注入的 `project_id`。
- 任务表持久化 `tenant_id + project_id + requested_by_user_id`。
- Worker 执行时按任务持久化上下文读取项目和租户配置，不读取当前前端 token。

## 前端状态

前端允许缓存：

- 当前 `tenant_id`
- 当前 `tenant_role` 快照
- 租户列表
- 当前 `project_id`
- 项目显示名

前端禁止：

- 把 role 作为真实授权依据。
- 向业务接口传入自选 `tenant_id` 或 role。
- 用项目名构造 API URL、缓存 key、SSE channel、localStorage 项目 key。

租户切换必须由用户手动触发。登录后默认进入个人空间。

## 验收审计清单

- [ ] 所有 `/projects/{name}` 路由改为 `/projects/{project_id}`。
- [ ] 所有项目文件路径使用 `project_id`。
- [ ] 所有 SQL 查询项目时带当前后端 tenant 上下文。
- [ ] 所有任务、Agent、文件、用量记录持久化 `tenant_id + project_id`。
- [ ] API key UI 和后台行为默认不可用。
- [ ] 用量统计支持 tenant/project 分组。
- [ ] 前端所有缓存 key 和 URL 不再使用项目名。
- [ ] 跨租户同名项目测试通过。
- [ ] view/member/admin/owner 权限矩阵测试通过。
- [ ] Agent 输入文本、生成图片、生成视频、上传文件、导入资产完整链路测试通过。
