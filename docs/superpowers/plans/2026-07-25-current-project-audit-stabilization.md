# Current Project Audit Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关闭 2026-07-25 项目审计中发现的租户隔离、安全、前端状态和质量门禁缺陷。

**Architecture:** 先修会造成生产隔离或用户可见错误的浅接口，再把重复的路由、HTTP、stream 和文档门禁收敛到更深的模块边界。每个任务必须先写能失败的回归测试，再写最小实现。

**Tech Stack:** Python 3.13、FastAPI、SQLAlchemy Async ORM、PostgreSQL RLS、React 19、Zustand、Vitest、pnpm、uv/conda。

## Global Constraints

- 回答、任务清单及计划文件使用中文。
- 运行 Python 命令使用 `.local/ENVS.md` 记录的模板：`/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel xxx.py`。
- 运行 JavaScript/TypeScript 命令使用 `.local/ENVS.md` 记录的模板：`/data/data1/HOME_DIR/sijin/.local/bin/pnpm xxx`。
- 不执行 `pip install`。
- 不主动停止、重启、kill 或替换用户现有服务进程。
- 新增面向用户文本必须补齐 `zh`、`en`、`vi` i18n key。
- Python 改动后对修改文件运行 `uv run ruff check <files> && uv run ruff format <files>` 的等价项目环境命令。
- 前端改动后在 `frontend/` 运行 `pnpm lint` 和相关 Vitest 文件。
- 当前工作树已有未提交改动；执行者不得 revert 非本人改动。

---

## File Structure

- `server/services/generation_tasks.py`: 修 credentialed backend cache key，保留 `invalidate_backend_cache()`。
- `tests/test_generation_tasks_service.py`: 增加 backend cache tenant isolation 回归测试，保留当前 custom provider resolution 测试。
- `server/services/resume_executor.py`: reference-video resume 调 finalizer 时传入 task/user/tenant file metadata。
- `tests/test_resume_executor.py`: 增加 reference-video resume 成功后把 metadata 传给 finalizer 的回归测试。
- `frontend/src/api.ts`: 增加 path segment encoder 并用于 project file URL 和 global asset URL。
- `frontend/src/api.test.ts`: 增加空格、`#`、`?`、`%` 和非 ASCII 文件名 URL 测试。
- `frontend/src/stores/config-status-store.ts`: 暴露 `reset()` 或 tenant-scoped refresh 入口，保证旧 tenant 状态不可继续被信任。
- `frontend/src/stores/auth-store.ts`: tenant token 切换成功后失效 config status。
- `frontend/src/stores/auth-store.test.ts`: 增加 tenant switch 后 config status 清空测试。
- `frontend/src/stores/projects-store.ts`: 让项目切换或清空时不保留上一项目 fingerprint。
- `frontend/src/stores/stores.test.ts`: 增加跨项目同 path fingerprint 不泄漏测试。
- `frontend/src/lib/stream-auth.ts`: 引入短期 stream token URL 构造入口。
- `frontend/src/lib/stream-auth.test.ts`: 验证长期 bearer token 不进入 SSE URL。
- `.github/workflows/test.yml`: 增加 docs gate job，docs-only PR 不再完全跳过验证。
- `scripts/docs_gate.py`: 检查 Markdown 链接、ADR frontmatter、`docs/INDEX.md` active backlog link。
- `tests/test_docs_gate.py`: 用临时 docs 树验证 docs gate 可发现坏链接和坏 ADR frontmatter。
- `docs/INDEX.md`、`CONTEXT.md`、相关 ADR/roadmap: 刷新 Active 计划和已落地状态。

---

### Task 1: Backend Cache Tenant Isolation

**Files:**
- Modify: `server/services/generation_tasks.py`
- Test: `tests/test_generation_tasks_service.py`

**Interfaces:**
- Consumes: `ConfigResolver(..., user_id, tenant_id)` 内部已有 `_user_id` 与 `_tenant_id`。
- Produces: `_get_or_create_{image,video,audio}_backend()` 使用 `(channel, tenant_id, user_id, provider_name, model)` 作为缓存 key。

- [ ] **Step 1: Write the failing test**

```python
async def test_backend_cache_is_scoped_by_tenant_and_user(monkeypatch):
    generation_tasks.invalidate_backend_cache()
    calls = []

    async def fake_assemble_backend(**kwargs):
        calls.append((kwargs["media_type"], kwargs["provider_id"], kwargs["model_id"]))
        return object()

    class Resolver:
        def __init__(self, user_id, tenant_id):
            self._user_id = user_id
            self._tenant_id = tenant_id

    monkeypatch.setattr(generation_tasks, "assemble_backend", fake_assemble_backend)

    first = await generation_tasks._get_or_create_video_backend(
        "ark",
        {"model": "seedance"},
        Resolver("user-a", "ten-a"),
    )
    second = await generation_tasks._get_or_create_video_backend(
        "ark",
        {"model": "seedance"},
        Resolver("user-b", "ten-b"),
    )

    assert first is not second
    assert calls == [("video", "ark", "seedance"), ("video", "ark", "seedance")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest tests/test_generation_tasks_service.py::TestGenerationTasks::test_backend_cache_is_scoped_by_tenant_and_user -q`

Expected: FAIL because the second call reuses the first cached backend.

- [ ] **Step 3: Write minimal implementation**

```python
def _backend_cache_key(channel: str, provider_name: str, model: str | None, resolver: ConfigResolver) -> tuple[str, str | None, str | None, str, str | None]:
    return (
        channel,
        getattr(resolver, "_tenant_id", None),
        getattr(resolver, "_user_id", None),
        provider_name,
        model,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest tests/test_generation_tasks_service.py::TestGenerationTasks::test_backend_cache_is_scoped_by_tenant_and_user -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/services/generation_tasks.py tests/test_generation_tasks_service.py
git commit -m "fix(generation): scope backend cache by tenant"
```

### Task 2: Reference Video Resume File Metadata

**Files:**
- Modify: `server/services/resume_executor.py`
- Test: `tests/test_resume_executor.py`

**Interfaces:**
- Consumes: task dict fields `task_id`, `user_id`, `tenant_id` and payload `script_file`。
- Produces: `_finalize_reference_video_unit(..., created_by_user_id, tenant_id, task_id)` receives the same metadata as the normal reference-video path.

- [ ] **Step 1: Write the failing test**

```python
async def test_reference_video_resume_passes_file_metadata_to_finalizer(monkeypatch, tmp_path):
    captured = {}

    async def fake_finalize(**kwargs):
        captured.update(kwargs)
        return {"video": "reference_videos/E1U1.mp4", "file_id": "fil_video_1"}

    monkeypatch.setattr(resume_executor, "_finalize_reference_video_unit", fake_finalize)

    result = await resume_executor.execute_resume_task(
        {
            "task_id": "task-1",
            "task_type": "video",
            "resource_id": "E1U1",
            "project_name": "demo",
            "user_id": "user-a",
            "tenant_id": "ten-a",
            "payload": {
                "generation_mode": "reference_video",
                "script_file": "episode_1.json",
                "provider_id": "vidu",
                "provider_job_id": "job-1",
            },
        }
    )

    assert captured["created_by_user_id"] == "user-a"
    assert captured["tenant_id"] == "ten-a"
    assert captured["task_id"] == "task-1"
    assert result["file_id"] == "fil_video_1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest tests/test_resume_executor.py::test_reference_video_resume_passes_file_metadata_to_finalizer -q`

Expected: FAIL because `created_by_user_id`、`tenant_id`、`task_id` are absent.

- [ ] **Step 3: Write minimal implementation**

```python
result = await _finalize_reference_video_unit(
    project_name=project_name,
    episode_file=payload.get("script_file") or "",
    unit_id=resource_id,
    video_path=video_path,
    created_by_user_id=task.get("user_id") or DEFAULT_USER_ID,
    tenant_id=task.get("tenant_id"),
    task_id=task.get("task_id"),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest tests/test_resume_executor.py::test_reference_video_resume_passes_file_metadata_to_finalizer -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/services/resume_executor.py tests/test_resume_executor.py
git commit -m "fix(reference-video): preserve file metadata on resume"
```

### Task 3: Frontend Media URL Segment Encoding

**Files:**
- Modify: `frontend/src/api.ts`
- Test: `frontend/src/api.test.ts`

**Interfaces:**
- Consumes: existing `API.getFileUrl(projectName, path, cacheBust)` and `API.getGlobalAssetUrl(path, fp)` callers.
- Produces: all path segments are encoded individually while `/` hierarchy remains intact.

- [ ] **Step 1: Write the failing test**

```typescript
it("encodes each project file path segment without collapsing slashes", () => {
  expect(API.getFileUrl("my project", "source/a #1?.txt", "v%1")).toBe(
    "/api/v1/files/my%20project/source/a%20%231%3F.txt?v=v%251",
  );
});

it("encodes global asset type and filename segments", () => {
  expect(API.getGlobalAssetUrl("_global_assets/character/角色 #1?.png", "fp%1")).toBe(
    "/api/v1/global-assets/character/%E8%A7%92%E8%89%B2%20%231%3F.png?fp=fp%251",
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && /data/data1/HOME_DIR/sijin/.local/bin/pnpm vitest run src/api.test.ts -- -t "encodes"`

Expected: FAIL because raw `#` and `?` remain in URLs.

- [ ] **Step 3: Write minimal implementation**

```typescript
function encodePathSegments(path: string): string {
  return path.split("/").map((segment) => encodeURIComponent(segment)).join("/");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && /data/data1/HOME_DIR/sijin/.local/bin/pnpm vitest run src/api.test.ts -- -t "encodes"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.ts frontend/src/api.test.ts
git commit -m "fix(frontend): encode media url path segments"
```

### Task 4: Tenant Switch Invalidates Config Status

**Files:**
- Modify: `frontend/src/stores/config-status-store.ts`
- Modify: `frontend/src/stores/auth-store.ts`
- Test: `frontend/src/stores/auth-store.test.ts`

**Interfaces:**
- Consumes: `useConfigStatusStore.getState().reset()`.
- Produces: successful `switchTenant()` clears stale config status before the next loader fetch.

- [ ] **Step 1: Write the failing test**

```typescript
it("invalidates config status after switching tenant", async () => {
  useConfigStatusStore.setState({
    initialized: true,
    isComplete: true,
    availableMediaTypes: ["image", "video", "text"],
  });
  useAuthStore.setState({
    token: "personal-token",
    isAuthenticated: true,
    currentTenant: personalTenant,
    tenants: [personalTenant, teamTenant],
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
    access_token: "team-token",
    token_type: "bearer",
    tenant: teamTenant,
  })));

  await useAuthStore.getState().switchTenant("ten_team");

  expect(useConfigStatusStore.getState()).toMatchObject({
    initialized: false,
    isComplete: false,
    availableMediaTypes: [],
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && /data/data1/HOME_DIR/sijin/.local/bin/pnpm vitest run src/stores/auth-store.test.ts -- -t "invalidates config status"`

Expected: FAIL because stale config status stays initialized.

- [ ] **Step 3: Write minimal implementation**

```typescript
reset: () => set({
  issues: [],
  availableMediaTypes: [],
  isComplete: false,
  loading: false,
  initialized: false,
  pendingRefresh: false,
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && /data/data1/HOME_DIR/sijin/.local/bin/pnpm vitest run src/stores/auth-store.test.ts -- -t "invalidates config status"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/config-status-store.ts frontend/src/stores/auth-store.ts frontend/src/stores/auth-store.test.ts
git commit -m "fix(frontend): reset config status on tenant switch"
```

### Task 5: Project Fingerprints Stay Project-Local

**Files:**
- Modify: `frontend/src/stores/projects-store.ts`
- Test: `frontend/src/stores/stores.test.ts`

**Interfaces:**
- Consumes: existing `setCurrentProject(name, data, scripts, fingerprints)`。
- Produces: setting a new project with no fingerprints or clearing the current project clears old fingerprints.

- [ ] **Step 1: Write the failing test**

```typescript
it("clears fingerprints when switching to a project without a fingerprint snapshot", () => {
  const store = useProjectsStore.getState();
  store.setCurrentProject("demo-a", {} as any, {}, { "storyboards/same.png": 1 });
  store.setCurrentProject("demo-b", {} as any, {});

  expect(useProjectsStore.getState().getAssetFingerprint("storyboards/same.png")).toBeNull();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && /data/data1/HOME_DIR/sijin/.local/bin/pnpm vitest run src/stores/stores.test.ts -- -t "clears fingerprints"`

Expected: FAIL because old fingerprints are retained.

- [ ] **Step 3: Write minimal implementation**

```typescript
assetFingerprints: fingerprints ?? {},
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && /data/data1/HOME_DIR/sijin/.local/bin/pnpm vitest run src/stores/stores.test.ts -- -t "clears fingerprints"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/projects-store.ts frontend/src/stores/stores.test.ts
git commit -m "fix(frontend): keep media fingerprints project-local"
```

### Task 6: Stream Auth Stops Exposing Long-Lived Bearer Tokens

**Files:**
- Create: `frontend/src/lib/stream-auth.ts`
- Test: `frontend/src/lib/stream-auth.test.ts`
- Modify: `frontend/src/api.ts`
- Modify: backend stream token router after API contract is chosen.

**Interfaces:**
- Consumes: existing stream URL builders for tasks, project events and assistant entries.
- Produces: SSE URL contains only a short-lived stream token or uses cookie-backed session; long-lived bearer token never appears in query strings.

- [ ] **Step 1: Write the failing test**

```typescript
it("does not append the long-lived bearer token to stream urls", async () => {
  const url = await buildStreamUrl("/api/v1/tasks/stream", {
    bearerToken: "long-lived-token",
    requestStreamToken: async () => "stream-token",
  });

  expect(url).toBe("/api/v1/tasks/stream?stream_token=stream-token");
  expect(url).not.toContain("long-lived-token");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && /data/data1/HOME_DIR/sijin/.local/bin/pnpm vitest run src/lib/stream-auth.test.ts`

Expected: FAIL because `buildStreamUrl` does not exist.

- [ ] **Step 3: Write minimal implementation**

```typescript
export async function buildStreamUrl(baseUrl: string, options: StreamAuthOptions): Promise<string> {
  const streamToken = await options.requestStreamToken();
  const separator = baseUrl.includes("?") ? "&" : "?";
  return `${baseUrl}${separator}stream_token=${encodeURIComponent(streamToken)}`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && /data/data1/HOME_DIR/sijin/.local/bin/pnpm vitest run src/lib/stream-auth.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/stream-auth.ts frontend/src/lib/stream-auth.test.ts frontend/src/api.ts
git commit -m "fix(frontend): use short-lived stream auth urls"
```

### Task 7: Docs Gate For Docs-Only Changes

**Files:**
- Create: `scripts/docs_gate.py`
- Create: `tests/test_docs_gate.py`
- Modify: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: repository root path.
- Produces: exit code 0 when docs links/frontmatter/index are valid; exit code 1 with concrete path messages when invalid.

- [ ] **Step 1: Write the failing test**

```python
def test_docs_gate_rejects_missing_active_backlog(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "INDEX.md").write_text(
        "| Date | Feature | Status | Sprint Backlog |\n"
        "|------|---------|--------|----------------|\n"
        "| 20260725 | broken | planned | [->](./missing/sprint-backlog.md) |\n",
        encoding="utf-8",
    )

    result = run_docs_gate(tmp_path)

    assert result.returncode == 1
    assert "docs/INDEX.md" in result.stderr
    assert "missing/sprint-backlog.md" in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest tests/test_docs_gate.py -q`

Expected: FAIL because `scripts/docs_gate.py` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def validate_docs_index(root: Path) -> list[str]:
    index = root / "docs" / "INDEX.md"
    errors = []
    for target in re.findall(r"\]\((\./[^)]+)\)", index.read_text(encoding="utf-8")):
      if not (index.parent / target).resolve().exists():
        errors.append(f"{index.relative_to(root)} missing link target {target}")
    return errors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest tests/test_docs_gate.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/docs_gate.py tests/test_docs_gate.py .github/workflows/test.yml
git commit -m "ci(docs): validate docs-only changes"
```

### Task 8: Documentation Drift Cleanup

**Files:**
- Modify: `CONTEXT.md`
- Modify: `docs/adr/0039-builtin-backend-construction-declarative-seam.md`
- Modify: reference-video roadmap files that still list existing PR plans as unwritten.
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: current code reality in `lib/backend_assembly`, `lib/generation_worker.py`, and existing reference-video plan files.
- Produces: docs state that matches the current code and Active plan.

- [ ] **Step 1: Write the failing verification command**

```bash
rg -n "真正接入还需|待写|status: proposed" CONTEXT.md docs/adr/0039-builtin-backend-construction-declarative-seam.md docs
```

Expected: Output includes stale lines that contradict current code reality.

- [ ] **Step 2: Patch docs with current evidence**

```markdown
status: accepted
```

- [ ] **Step 3: Run verification command**

Run: `rg -n "真正接入还需|待写|status: proposed" CONTEXT.md docs/adr/0039-builtin-backend-construction-declarative-seam.md docs`

Expected: No output for the corrected files; remaining output belongs to unrelated planned work and is listed in the commit message body.

- [ ] **Step 4: Commit**

```bash
git add CONTEXT.md docs/adr/0039-builtin-backend-construction-declarative-seam.md docs/INDEX.md docs/20260725/current-project-audit-and-stabilization/sprint-backlog.md
git commit -m "docs: refresh audit stabilization plan"
```

---

## Final Verification

- Run: `git diff --check`
- Run: `cd frontend && /data/data1/HOME_DIR/sijin/.local/bin/pnpm lint`
- Run: `cd frontend && /data/data1/HOME_DIR/sijin/.local/bin/pnpm check`
- Run targeted Python tests touched by this plan with the `.local/ENVS.md` Python template.
- Run PostgreSQL-backed tests only after `DATABASE_URL` is set; if unset, record the exact blocked command and do not claim those tests passed.
- Run: `git status --short`
- Commit all remaining staged and unstaged work once verification evidence is collected.
