# 最终交付：租户、用户、项目三层关系与权限限制

**日期:** 20260711  
**状态:** current  
**适用范围:** ArcReel 新商业发行版；不做旧项目、旧本地数据库、旧项目名路由兼容。

## 1. 三层业务关系

ArcReel 当前商业发行版只承认三个稳定业务 ID：

```text
User <-- TenantMembership --> Tenant <-- Project
```

| 层级 | ID | 归属与作用 | 禁止事项 |
|------|----|------------|----------|
| User | `user_id` | ArcReel 内部用户。身份从 CaMeL 登录导入，ArcReel 只做本地用户映射。 | 不用 username、display name、CaMeL 展示名做授权键。 |
| Tenant | `tenant_id` | 权限、系统配置、provider 凭证、资产库、项目集合、用量统计的边界。 | 前端不得在业务请求里自选 tenant_id。 |
| Project | `project_id` | 项目唯一业务键。项目只属于一个 tenant。 | 不用项目 name 做路由键、路径键、任务键、session 键、用量聚合键。 |

核心不变量：

1. `projects.tenant_id` 必须存在；一个项目只属于一个租户。
2. User 与 Tenant 是多对多，通过 `tenant_memberships` 授权。
3. User 与 Project 没有直接授权表；用户能否访问项目由当前租户 membership 决定。
4. `projects.name` 只用于 UI 展示和租户内重名校验，允许跨租户重复。
5. 所有项目业务查询都必须是 `tenant_id + project_id`。
6. 所有授权都以后端实时查询 membership 为准，不相信前端传来的 role 或 tenant_id。

## 2. 登录与当前租户

登录来源：

- 账号授权登录走 CaMeL。
- ArcReel 在本地创建或更新 `users` 映射。
- 用户首次登录时创建个人租户，默认名称为 `{user_name}的个人空间`。
- 登录后默认进入个人空间；切换租户必须由用户手动触发。

JWT 规则：

- access token 可包含 `user_id + tenant_id + tenant_role`。
- `tenant_role` 只是 UI 快照，用于展示和 stale refresh。
- 后端遇到请求时必须按 `user_id + tenant_id` 查真实 membership。
- 如果 token role 快照比真实 membership 旧，后端返回可识别错误，前端刷新当前租户 token 后重试用户主动发出的请求。

## 3. 租户角色与权限矩阵

第一版 membership role 只保留：

- `admin`
- `member`
- `view`

`owner` 不是 membership role。`owner_user_id` 是 `tenants` 表字段。owner 默认拥有 admin 行为，并额外拥有添加 admin 的能力。owner 转移暂不实现，但数据模型和服务边界预留，不允许卡死。

| 动作 | owner | admin | member | view |
|------|-------|-------|--------|------|
| 查看项目列表/详情 | 是 | 是 | 是 | 是 |
| 查看资产库 | 是 | 是 | 是 | 是 |
| 查看成员列表 | 是 | 是 | 是 | 是 |
| 查看用量 | 是 | 是 | 是 | 是 |
| 创建项目 | 是 | 是 | 是 | 否 |
| 导入源文件 | 是 | 是 | 是 | 否 |
| 上传项目文件/媒体 | 是 | 是 | 是 | 否 |
| 生成文本/图片/视频/音频 | 是 | 是 | 是 | 否 |
| 导入资产到租户/个人库 | 是 | 是 | 是 | 否 |
| 编辑剧本、分镜、资源内容 | 是 | 是 | 是 | 否 |
| 编辑项目元数据/租户配置/provider | 是 | 是 | 否 | 否 |
| 删除项目 | 是 | 是 | 否 | 否 |
| 添加 viewer | 是 | 是 | 是 | 否 |
| 添加 member | 是 | 是 | 否 | 否 |
| 添加 admin | 是 | 否 | 否 | 否 |

成员添加限制：

- 只能添加 ArcReel 已激活用户。
- ArcReel 不做账号注册、密码、邮件验证业务；账号生命周期由 CaMeL 负责。

## 4. 项目访问规则

项目 API 路由统一使用 `project_id`：

```text
/api/v1/projects/{project_id}
/api/v1/projects/{project_id}/...
```

后端处理顺序：

```text
解析 access token
  -> 得到 user_id + tenant_id + role snapshot
  -> 查询 tenant_memberships
  -> 按 tenant_id + project_id 查询 projects
  -> 判断 action permission
  -> 执行业务 service
```

错误策略：

| 场景 | HTTP | 原则 |
|------|------|------|
| 未登录 | 401 | 没有有效身份 |
| token 缺当前 tenant | 401/403 | 不能进入业务上下文 |
| 当前用户不是租户成员 | 403 | 拒绝访问 |
| 项目不存在或不属于当前租户 | 404 | 避免跨租户枚举 |
| membership 存在但权限不足 | 403 | 明确权限不足 |
| role 快照过期 | 403 | 前端刷新当前租户 token 后重试 |

## 5. 存储与文件规则

数据库：

- 只支持 PostgreSQL。
- `DATABASE_URL` 必须是 `postgresql+asyncpg://...`。
- 不支持 SQLite、`.arcreel.db`、旧本地文件数据库迁移。

项目路径：

```text
$ARCREEL_DATA_DIR/_tenants/{tenant_id}/projects/{project_id}/project.json
```

文件：

- 所有文件都必须进入 `files` 表。
- 底层对象 key 使用 UUID 样式，例如 `aaaa-bbbb-cccc-dddd.ext`。
- 真实文件名只作为 `alias` 保存。
- MinIO bucket 保持私有。
- 前端访问文件走后端校验后的短签名 URL。
- 后端服务内部读取文件走 service 层，不依赖前端签名 URL。
- 文件与项目、资产、任务之间通过 `file_links` 绑定。

第一版策略：

- 不保留旧项目兼容。
- `project.json` 内资源引用转为 id/file_id 形式。
- 媒体产物迁移到 MinIO；必要的本地项目结构只作为项目元数据和开发期工作区存在。

## 6. 配置、provider 与 CaMeL bootstrap

Tenant 承载系统配置：

- text/image/video/audio provider 默认值
- custom providers
- Agent Anthropic Bridge 凭证
- 其他项目生成相关配置

CaMeL bootstrap 负责创建并写入当前租户的 provider/agent credential：

| media | 默认模型 |
|-------|----------|
| text | `gpt-5.5` |
| image | `gpt-image-2` |
| video | `doubao-seedance-2-0-260128` |
| audio | `gpt-4o-mini-tts` |
| anthropic | `claude-opus-4-8` |

CaMeL provider provisioning keys、媒体供应商凭证、Anthropic Bridge / Agent 凭证不属于 Issued Tokens 禁用范围。

## 7. Issued Tokens 暂停策略

这里的 Issued Tokens 指设置页里“API 密钥管理 / Issued Tokens”，用于 OpenClaw 等外部工具访问 ArcReel 项目。

当前版本要求：

- 后台 `GET/POST/PATCH/DELETE /api/v1/api-keys` 统一返回 `403 feature_disabled`。
- 外部同步 Agent 入口 `POST /api/v1/agent/chat` 统一返回 `403 feature_disabled`。
- 前端保留 UI，但按钮 disabled，不能触发创建、更新、删除请求。
- 已保留业务代码，后续显式启用时继续按 `user_id + tenant_id + project_id` 权限模型设计。

## 8. 资产库与快照绑定

资产分两类：

- 租户资产库
- 个人资产库

资产导入规则：

- member/admin/owner 可导入资产。
- view 只能查看。
- 跨租户或个人导入不复制底层文件，复用同一份 `file_id` / 底层对象引用。
- binding 包含 `parent_id`，形成快照链。
- sync 第一版为手动触发。

## 9. 用量统计

用量事实表按 ID 存：

- `tenant_id`
- `project_id`
- `user_id`
- `task_id`
- `provider_id`
- `model`
- `media_type`
- `operation`
- `cost`
- `created_at`

展示允许按以下维度聚合：

- tenant
- project
- user
- provider
- model
- media_type
- day

禁止按项目名称聚合。项目名称只允许作为 join 后的展示字段。

## 10. Agent、任务与多项目并行

多 project、多任务并行的隔离边界是：

```text
tenant_id + project_id + session_id/task_id
```

Agent 规则：

- 会话创建和消息发送路由使用 `project_id`。
- session metadata 保存 `tenant_id + project_id + user_id`。
- session 读取、entries 读取、interrupt、delete 都必须校验 route `project_id` 与 session `project_id` 一致。
- Agent cwd 由 `tenant_id + project_id` 计算。
- MCP 工具不接受用户传入的项目名推断；项目上下文由 session 注入。

MCP / Skill session 规则：

- 每个 assistant session 构造独立的 in-process MCP server，工具闭包绑定当前 `project_id` 对应的项目根。
- MCP 工具执行时必须进入 `user_id + tenant_id` identity scope；队列任务、文本/媒体调用、用量落账都从当前 session 继承身份。
- MCP 工具参数不得接受 `tenant_id`、`role` 或任意项目路径前缀作为授权或落点依据。
- Skill 只能在当前 session cwd 下工作；项目 JSON 和剧本 JSON 的写入必须走 MCP 编辑工具。
- Skill 脚本只允许作为已登记 runtime profile 的项目内脚本运行，且输出必须落在当前项目允许目录内，例如 `output/`。
- Write / Edit / Bash 直改 `project.json` 或 `scripts/` 必须被 sandbox denyWrite 与 PreToolUse hook 双层拒绝。
- 任何后台 session store、transcript、event log、usage、task row 都必须至少携带 `tenant_id + project_id/session_id`，避免多项目并发时落到默认租户或同名项目。

任务规则：

- 入队时检查当前用户权限。
- task 持久化 `tenant_id + project_id + requested_by_user_id`。
- worker 执行时读取 task 持久化上下文和租户配置。
- 已提交任务不因后续 membership 变化自动取消。
- 用户发起新请求时重新按最新 membership 判断权限。

这保证多项目并行时不会因项目 display name 重复、前端切换租户、角色变化或多个 Agent session 同时运行导致保存串项目、存档串项目。

## 11. 前端状态边界

前端允许缓存：

- 当前 access token
- 当前租户列表
- 当前租户 role 快照
- 当前项目 id
- 项目显示名

前端禁止：

- 传 role 给业务接口作为授权依据。
- 传自选 tenant_id 给项目业务接口。
- 用项目 name 构造 API URL、SSE channel、任务 filter、localStorage 项目 key。
- 以 UI disabled 代替后端鉴权。

## 12. 当前验证结论

已验证：

- PostgreSQL-only schema 和迁移路径。
- SQLite 旧文档已删除或收敛为审计记录。
- session/task/usage 存储列使用 `project_id`。
- 同一租户内多 project 的 session list、task cancel-all、task events 均按 `project_id` 隔离。
- 前端右侧智能体最后会话缓存按项目 id 隔离，重复显示名不会交叉加载 session。
- Issued Tokens 后台 403、前端 disabled。
- tenant role stale refresh。
- owner/admin/member/view 权限矩阵关键路径。
- 本地清库后，默认个人租户、project_id 项目创建、源文件导入、文件列表、assistant session 创建均可运行。
- 浏览器冒烟显示默认个人空间、租户 listbox、项目列表和 CaMeL bootstrap modal。

未完成的模型侧验证：

- 本地真实 CaMeL OAuth 因 `http://127.0.0.1:1241/api/v1/auth/camel/callback` 未在 CaMeL client 注册，无法在本机完成真实 provider bootstrap。
- 因 provider bootstrap 未完成，本机无法证明真实文本/图片模型生成链路。
- 该阻断不允许通过修改 `camel-api`、猜测 password grant 或添加 fallback 规避；只能在已注册 redirect URI 的 ArcReel 环境或 CaMeL client 配置修正后继续验证。
