# Preflight Audit: CaMeL OAuth And Provider Bootstrap

**Date:** 20260710
**Scope:** 审计租户商业化改造依赖的前置能力：CaMeL OAuth 登录、ArcReel 用户 upsert、ArcReel API key owner 解析、CaMeL provider/API key bootstrap。

## Verdict

ArcReel 侧 CaMeL OAuth 登录、provider bootstrap、repair、API key owner 解析的主体路径已经可用，可以作为租户化设计的前置基础。

但 CaMeL-api 侧 ArcReel token provisioning 还不能算完全完成：它接收 `idempotency_key`，但没有实际使用；并且没有针对 ArcReel provisioning 的 Go 专项测试。这个缺口需要作为租户商业化 sprint 的前置修复 story。

## Verified Evidence

ArcReel 侧测试：

```text
/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest \
  tests/test_camel_auth_provider_bootstrap.py \
  tests/test_camel_bootstrap_service.py \
  tests/test_auth_api_key.py \
  tests/test_api_keys_router.py -q

32 passed, 1 warning in 0.56s
```

CaMeL-api 侧相关包测试：

```text
go test ./model ./controller -run 'ArcReel|OAuthProviderArcReel|ProvisionArcReel'

ok github.com/QuantumNous/new-api/model [no tests to run]
ok github.com/QuantumNous/new-api/controller [no tests to run]
```

这说明 Go 包可编译，但当前没有覆盖 ArcReel provisioning 的专项测试。

## Findings

### Finding 1: CaMeL-api ignores ArcReel provisioning idempotency key

**Severity:** major
**Files:**

- `../CaMeL-api/controller/oauth_provider_arcreel.go:14`
- `../CaMeL-api/controller/oauth_provider_arcreel.go:49`
- `../CaMeL-api/model/arcreel_token.go:24`
- `../CaMeL-api/model/arcreel_token.go:47`

`arcReelTokenProvisionRequest` 接收 `idempotency_key`，但 `OAuthProviderArcReelTokens` 构造 `model.ArcReelProvisionRequest` 时没有传入这个字段，`ArcReelProvisionRequest` 模型也没有该字段，`ProvisionArcReelTokens` 内没有任何幂等记录或复用逻辑。

影响：

- 浏览器/OAuth callback 在 CaMeL 创建 token 后、ArcReel 收到响应前断线时，同一个 `idempotency_key` 重试不能复用第一次结果。
- `mode=create` 第二次请求会看到同名 token 已存在，然后返回 `token_name_conflict`。
- 对首次初始化 API key 来说，这是可见失败，不符合“初始化动作可安全重试”的要求。

要求：

- CaMeL-api 增加 ArcReel provisioning 幂等记录，key 至少包含 `user_id + client_id + idempotency_key`。
- 首次成功后，重试同一 key 返回同一组 token 结果或一个明确的 already-completed 响应。
- 幂等记录不应长期保存 plaintext key；如果无法安全重放明文 key，则 ArcReel 侧应把 create 流程改成“成功创建但本地失败时要求 repair”，并 contract 明确说明。

### Finding 2: CaMeL-api has no ArcReel provisioning unit/integration tests

**Severity:** major
**Files:**

- `../CaMeL-api/controller/oauth_provider_arcreel.go`
- `../CaMeL-api/model/arcreel_token.go`

`rg` 没有找到 `*_test.go` 里覆盖 `ArcReel` / `ProvisionArcReelTokens` / `OAuthProviderArcReelTokens` 的测试。`go test ./model ./controller -run 'ArcReel|OAuthProviderArcReel|ProvisionArcReel'` 返回 `[no tests to run]`。

必须补的测试：

- create 成功创建四个 visible token，`managed_by=arcreel`，按 media 写入 model limits。
- create 遇到同名非 ArcReel-managed token 时返回 conflict，且不创建任何 token。
- repair 可旋转 ArcReel-managed token，不能旋转非 ArcReel-managed token。
- bearer token 必须属于 ArcReel OAuth client。
- bearer token 必须包含 `arcreel:token-provision` scope。
- idempotency retry 行为。

### Finding 3: ArcReel OAuth dynamic redirect trusts `X-Forwarded-Proto` without scheme allowlist

**Severity:** medium
**File:** `server/services/camel_auth.py:115`

`_camel_redirect_uri()` 在 host 命中 `CAMEL_OAUTH_REDIRECT_HOSTS` 后直接使用 `x-forwarded-proto` 构造 `redirect_uri`。它没有限制 scheme 只能是 `http` 或 `https`。

影响：

- 在代理配置不严格时，客户端可影响 OAuth `redirect_uri` scheme。
- CaMeL 正常应通过已注册 redirect URI 拒绝异常 scheme，但 ArcReel 侧仍应 fail closed，避免把安全性押在外部服务上。

要求：

- 只接受 `http`/`https`。
- 生产环境建议只允许 `https`。
- 对非法 forwarded proto 返回 400。

### Finding 4: Current API key name is globally unique, not user-scoped

**Severity:** medium
**File:** `lib/db/models/api_key.py:17`

`ApiKey.name` 当前是全局 unique。虽然 API key list/delete/create 通过 `user_id` repository scope 隔离，但两个用户不能创建同名 API key。

影响：

- 当前 CaMeL user isolation 下，用户之间仍存在 API key 名称冲突。
- 租户化后必须改为 `unique(tenant_id, name)` 或 `unique(tenant_id, created_by_user_id, name)`，否则团队租户和个人空间会互相影响。

要求：

- 在租户化 schema story 中删除全局 name unique。
- 新约束按租户定义。

### Finding 5: Bootstrap status only checks timestamp, not actual provider completeness

**Severity:** minor
**File:** `server/services/camel_bootstrap.py:203`

`get_camel_bootstrap_status()` 只看 `users.camel_provider_bootstrap_completed_at`。如果用户后续删除了 CaMeL providers 或默认配置，status 仍返回 completed。

影响：

- 首次登录弹窗不会自动修复缺失 provider。
- 当前已有 repair 入口，问题可绕过。
- 租户化后如果要把 provider 初始化绑定到个人空间，需要改成按 tenant config/provider 完整性判断。

要求：

- 商业化新版本里不要复用 user-level timestamp 作为唯一完成依据。
- 改为 tenant-level bootstrap state，并校验关键 provider/default 是否存在。

### Finding 6: CaMeL display username uniqueness may become tenant onboarding blocker

**Severity:** minor
**Files:**

- `server/services/camel_auth.py:250`
- `lib/db/models/user.py:16`

`upsert_camel_user()` 用 CaMeL `username` 或 `display_name` 写入 `users.username`，而 `users.username` 是 unique。只要 CaMeL 保证 username 全局唯一就没有问题；如果回落到 display_name，唯一约束会变成登录风险。

要求：

- 租户化新 schema 中把用户唯一身份绑定到 provider subject，不把 display name 当唯一键。
- `username/display_name` 只做展示字段。

## Conclusion For Tenant Commercialization

可以继续基于现有 CaMeL OAuth 和 ArcReel bootstrap 设计租户系统，但 sprint 必须加入一个前置 story：

1. 修复 CaMeL-api ArcReel token provisioning idempotency。
2. 为 CaMeL-api 添加 ArcReel provisioning 专项测试。
3. 在 ArcReel 侧收紧 dynamic redirect scheme。
4. 在租户化 schema 中顺带移除 API key name 全局唯一和 user-level bootstrap timestamp 依赖。
