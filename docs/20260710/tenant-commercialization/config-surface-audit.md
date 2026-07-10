# 租户商业版配置面审计

审计日期：2026-07-10

审计对象：`integration/tenant-commercialization` 当前新项目实现。

## 实施结果

2026-07-10 已按审计结论完成第一轮收敛：

- `CAMEL_ARCREEL_*` 不再出现在 ArcReel 的 `.env.example`、`deploy/.env.example` 和测试 compose 必要运行参数中。
- ArcReel 在 CaMeL token provisioning 请求中携带 `media_specs`，媒体类型、endpoint 映射和 model 清单由 ArcReel bootstrap settings 统一拥有。
- CaMeL-api 侧移除了 ArcReel image/text/video/audio model 默认值和 model env 读取，只按 ArcReel 请求传入的 `media_specs` 创建/修复 token。
- `ARCREEL_FILE_STORAGE_BACKEND` 已从 ArcReel env 模板移除；当前发行版明确固定使用 MinIO。

## 结论

当前最大初始化风险不是租户权限、PG、Redis 或 MinIO，而是 CaMeL 供应商引导参数被拆成了过多必填环境变量。

按现在的 `.env.example` / `deploy/.env.example`，一个部署者会看到 30 个以上环境变量；其中第一次 CaMeL provider bootstrap 会被 11 个 `CAMEL_ARCREEL_*` 变量硬性阻断。这个配置面过浅：调用者必须理解 CaMeL token provisioning URL、provider base URL、token 管理链接、四类媒体 endpoint、四类媒体 model 列表，才能完成一个本应由产品预设解决的初始化动作。

推荐把“普通部署必须填写”的参数压到 8 到 10 个以内，把其余参数转为代码预设、派生值或高级覆盖项。

## 当前配置面分层

| 层级 | 当前变量 | 审计判断 |
|---|---|---|
| 启动必需 | `DATABASE_URL` | 合理。租户版强制 PG，代码在 import 期 fail-fast。 |
| 商业版认证必需 | `AUTH_MODE=camel`、`AUTH_TOKEN_SECRET`、`CAMEL_OAUTH_BASE_URL`、`CAMEL_OAUTH_CLIENT_ID`、`CAMEL_OAUTH_CLIENT_SECRET`、`CAMEL_OAUTH_REDIRECT_URI` 或 `CAMEL_OAUTH_REDIRECT_HOSTS` | `AUTH_MODE=camel` 目前未在主要 env 模板中显式列出，是隐患。 |
| 中间件连接 | `REDIS_URL`、`ARCREEL_MINIO_ENDPOINT`、`ARCREEL_MINIO_PUBLIC_ENDPOINT`、`ARCREEL_MINIO_ACCESS_KEY`、`ARCREEL_MINIO_SECRET_KEY` | 生产需要明确；dev compose 已有默认值。Redis 缺失时权限缓存会静默关闭，不阻断启动。 |
| 可派生 | `CAMEL_OAUTH_INTERNAL_BASE_URL`、`CAMEL_OAUTH_SCOPES`、`CAMEL_OAUTH_BOOTSTRAP_SCOPES`、`CAMEL_OAUTH_REPAIR_MAX_AGE_SECONDS`、`ARCREEL_MINIO_BUCKET`、`ARCREEL_MINIO_REGION`、`ARCREEL_SIGNED_URL_TTL_SECONDS` | 都已有默认或可从 base URL / 产品策略派生，不应出现在最小初始化清单。 |
| 应改成产品预设 | `CAMEL_ARCREEL_PROVIDER_BASE_URL`、`CAMEL_ARCREEL_TOKEN_PROVISION_URL`、`CAMEL_ARCREEL_TOKEN_LINK_TEMPLATE`、`CAMEL_ARCREEL_IMAGE_ENDPOINT`、`CAMEL_ARCREEL_IMAGE_MODELS`、`CAMEL_ARCREEL_TEXT_ENDPOINT`、`CAMEL_ARCREEL_TEXT_MODELS`、`CAMEL_ARCREEL_VIDEO_ENDPOINT`、`CAMEL_ARCREEL_VIDEO_MODELS`、`CAMEL_ARCREEL_AUDIO_ENDPOINT`、`CAMEL_ARCREEL_AUDIO_MODELS` | 当前最大问题。普通部署者不应逐项填写。 |
| 运营可选 | `LOG_LEVEL`、`ARCREEL_LOG_DIR`、`ARCREEL_LOG_FILE_DISABLED`、`ARCREEL_DATA_DIR`、`ARCREEL_PROFILE_DIR`、`ARCREEL_SDK_SESSION_STORE`、`ASSISTANT_MAX_TURNS`、`ASSISTANT_STREAM_HEARTBEAT_SECONDS` | 保持可选。不要进入首次初始化路径。 |
| 前端构建可选 | `VITE_BRAND_*`、`VITE_ARCREEL_LEGAL_*` | 与运行时初始化无关，可作为发行合规/品牌配置保留。 |

## 具体发现

### 1. `CAMEL_ARCREEL_*` 是当前唯一高风险参数群

证据：

- `server/services/camel_bootstrap.py` 的 `get_camel_bootstrap_settings()` 对 11 个 `CAMEL_ARCREEL_*` 变量全部调用 `_env()`。
- `_env()` 空值直接抛出 `503 {name} is not configured`。
- `tests/test_camel_bootstrap_service.py` 和 `tests/test_tenant_config_isolation.py` 为了跑 bootstrap，必须重复设置完整 11 项。

问题：

- endpoint 和 model 列表属于 ArcReel × CaMeL 发行版的产品契约，不是每个部署者的初始化输入。
- `CAMEL_ARCREEL_TOKEN_PROVISION_URL` 可从 `CAMEL_OAUTH_INTERNAL_BASE_URL` 或 `CAMEL_OAUTH_BASE_URL` 派生。
- `CAMEL_ARCREEL_TOKEN_LINK_TEMPLATE` 可从 `CAMEL_OAUTH_BASE_URL` 派生。
- `CAMEL_ARCREEL_PROVIDER_BASE_URL` 可默认等于 `CAMEL_OAUTH_INTERNAL_BASE_URL`。

建议：

- 新增一个深模块，例如 `CamelBootstrapPresetResolver`。
- 对外 interface 只保留：
  - `CAMEL_ARCREEL_PRESET=camel-default`
  - 可选高级覆盖：`CAMEL_ARCREEL_PRESET_JSON` 或单个 override 变量。
- 默认 preset 内置四类媒体：
  - image: `openai-images` / `camel-image`
  - text: `openai-chat` / `camel-text`
  - video: `ark-seedance` / `doubao-seedance-2-0-260128`
  - audio: `openai-tts` / `camel-audio`

### 2. `AUTH_MODE=camel` 缺少模板显式引导

证据：

- `server/auth.py` 默认 `AUTH_MODE` 为 `local`。
- 当前租户商业版登录授权链路依赖 CaMeL。
- 根 `.env.example` 与 `deploy/.env.example` 都没有显式列出 `AUTH_MODE=camel`。

影响：

- 部署者可能填了 CaMeL OAuth 参数，但系统仍走本地账号登录。
- 这类问题不一定启动失败，会变成运行时路径错误。

建议：

- 商业版最小模板显式写入 `AUTH_MODE=camel`。
- 本地账号变量 `AUTH_USERNAME` / `AUTH_PASSWORD` 从商业版最小模板移到 legacy/local auth 模板。

### 3. MinIO 配置已经有默认值，但 env 模板暴露过多

证据：

- `lib/storage/minio.py::MinIOSettings.from_env()` 已为 endpoint、public endpoint、access key、secret key、bucket、region 提供默认值。
- `deploy/dev/docker-compose.middleware.yml` 已固定 MinIO 版本，并创建私有 bucket。

问题：

- dev 场景不需要用户填写 6 个 MinIO 变量。
- 生产场景真正需要的是外部访问域名和密钥，bucket/region/TTL 可以默认。

建议：

- 最小模板只保留：
  - `ARCREEL_MINIO_PUBLIC_ENDPOINT`
  - `ARCREEL_MINIO_ACCESS_KEY`
  - `ARCREEL_MINIO_SECRET_KEY`
- `ARCREEL_MINIO_ENDPOINT` 在 compose 部署中固定为 `http://minio:9000`。
- `ARCREEL_MINIO_BUCKET`、`ARCREEL_MINIO_REGION`、`ARCREEL_SIGNED_URL_TTL_SECONDS` 移到高级模板。

### 4. `ARCREEL_FILE_STORAGE_BACKEND` 是误导性参数

证据：

- 搜索结果显示运行时代码没有读取 `ARCREEL_FILE_STORAGE_BACKEND`。
- `lib/storage/__init__.py` 直接导出 MinIO storage；上传、签名、生成产物都调用 `get_storage_service()`。

影响：

- 模板暗示可以选择 storage backend，但实现已经固定 MinIO。
- 这会制造无效配置和排错噪声。

建议：

- 从 env 模板删除 `ARCREEL_FILE_STORAGE_BACKEND`。
- 如果要预留未来多存储实现，保留在设计文档，不要暴露为当前可用配置。

### 5. Redis 缺失不会阻断，但商业版语义上应当可诊断

证据：

- `server/services/permission_cache.py::get_permission_cache()` 在 `REDIS_URL` 为空时返回 `None`。
- 权限校验会回源 DB，不会因为 Redis 缺失 fail。

判断：

- 这对安全是可接受的，因为真实权限仍查后端。
- 但对商业版运维不是可观察的：缓存关闭只表现为性能变化。

建议：

- 启动诊断输出 `permission_cache=disabled|redis`。
- 最小模板保留 `REDIS_URL`，但允许 compose 默认值覆盖。

### 6. 前端构建参数不应混入后端初始化清单

证据：

- 前端只读取品牌和 AGPL/legal 相关 `VITE_*`。
- 这些变量都有默认值，除 `sourceUrl` 合规提示外不阻断运行时。

建议：

- 单独提供 `frontend/.env.branding.example` 或文档章节。
- 不进入“启动 ArcReel 租户版”的最小 checklist。

## 推荐最小初始化清单

### compose 一体化部署

普通部署者只应填写：

```env
AUTH_MODE=camel
AUTH_TOKEN_SECRET=
POSTGRES_PASSWORD=
CAMEL_OAUTH_BASE_URL=
CAMEL_OAUTH_CLIENT_ID=
CAMEL_OAUTH_CLIENT_SECRET=
CAMEL_OAUTH_REDIRECT_URI=
ARCREEL_MINIO_PUBLIC_ENDPOINT=
ARCREEL_MINIO_ACCESS_KEY=
ARCREEL_MINIO_SECRET_KEY=
```

如果 ArcReel 和 CaMeL 在不同内网地址通信，再补：

```env
CAMEL_OAUTH_INTERNAL_BASE_URL=
```

### 本地开发

本地开发应尽量做到：

```env
AUTH_MODE=camel
AUTH_TOKEN_SECRET=dev-secret
CAMEL_OAUTH_BASE_URL=http://localhost:13080
CAMEL_OAUTH_CLIENT_ID=arc-client
CAMEL_OAUTH_CLIENT_SECRET=
CAMEL_OAUTH_REDIRECT_URI=http://localhost:1241/api/v1/auth/camel/callback
```

PG、Redis、MinIO 均由 `deploy/dev/docker-compose.middleware.yml` 的默认值提供。

## 建议拆分任务

1. 新增 `CamelBootstrapPresetResolver`，让 `CAMEL_ARCREEL_*` 变成 preset 默认值而不是必填项。
2. 更新 `tests/test_camel_bootstrap_service.py`，增加“只设置 OAuth + preset 即可返回完整 bootstrap plan”的测试。
3. 更新 `.env.example` / `deploy/.env.example`：拆成最小模板和高级模板。
4. 从模板移除 `ARCREEL_FILE_STORAGE_BACKEND`，或者实现真实 backend switch；二选一，不保留假配置。
5. 增加启动配置诊断：输出 blocking / degraded / optional 三类状态，覆盖 PG、CaMeL、Redis、MinIO、storage bucket private 检查。
