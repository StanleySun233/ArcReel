"""Tests for GenerationQueue (async wrapper over TaskRepository)."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import lib.generation_queue as generation_queue_module
from lib.generation_queue import GenerationQueue
from lib.generation_queue_client import enqueue_task_only
from lib.user_scope import current_identity_scope
from tests.pg_utils import create_pg_test_engine, drop_pg_test_engine


class _FakePostgresBind:
    dialect = type("Dialect", (), {"name": "postgresql"})()


class _FakePostgresSession:
    def __init__(self) -> None:
        self.info = {"tenant_id": "ten_old", "user_id": "camel:old"}
        self.calls: list[tuple[str, dict | None]] = []

    def get_bind(self):
        return _FakePostgresBind()

    async def execute(self, stmt, params=None):
        self.calls.append((str(stmt), params))


@pytest.fixture
async def queue():
    """Create a GenerationQueue backed by an isolated PostgreSQL schema."""
    engine, schema = await create_pg_test_engine()

    factory = async_sessionmaker(engine, expire_on_commit=False)
    q = GenerationQueue(session_factory=factory)
    try:
        yield q
    finally:
        await drop_pg_test_engine(engine, schema)


class TestGenerationQueue:
    async def test_prepare_worker_session_sets_explicit_worker_rls_context(self):
        session = _FakePostgresSession()

        await generation_queue_module._prepare_worker_session(session)

        assert "tenant_id" not in session.info
        assert session.info["user_id"] == "default"
        assert session.info["auth_mode"] == "worker"
        assert session.calls
        sql, params = session.calls[0]
        assert "app.auth_mode" in sql
        assert "'worker'" in sql
        assert params == {"user_id": "default"}

    async def test_enqueue_dedupe_claim_and_succeed(self, queue):
        first = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S01",
            payload={"prompt": "test"},
            script_file="episode_01.json",
            source="webui",
        )
        assert not first["deduped"]

        deduped = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S01",
            payload={"prompt": "test2"},
            script_file="episode_01.json",
            source="webui",
        )
        assert deduped["deduped"]
        assert deduped["task_id"] == first["task_id"]

        running = await queue.claim_next_task(media_type="image")
        assert running is not None
        assert running["task_id"] == first["task_id"]
        assert running["status"] == "running"

        rows = await queue.mark_task_succeeded(first["task_id"], {"file_path": "storyboards/scene_E1S01.png"})
        assert rows == 1
        done = await queue.get_task(first["task_id"])
        assert done is not None
        assert done["status"] == "succeeded"
        assert done["result"]["file_path"] == "storyboards/scene_E1S01.png"

        # 终态后允许再次入队
        second = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S01",
            payload={"prompt": "test3"},
            script_file="episode_01.json",
            source="webui",
        )
        assert not second["deduped"]
        assert second["task_id"] != first["task_id"]

    async def test_event_sequence_and_incremental_read(self, queue):
        task = await queue.enqueue_task(
            project_name="demo",
            task_type="video",
            media_type="video",
            resource_id="E1S01",
            payload={"prompt": "video"},
            script_file="episode_01.json",
            source="skill",
        )
        await queue.claim_next_task(media_type="video")
        await queue.mark_task_failed(task["task_id"], "mock error")

        all_events = await queue.get_events_since(last_event_id=0)
        assert len(all_events) >= 3
        assert all_events[0]["event_type"] == "queued"
        assert all_events[1]["event_type"] == "running"
        assert all_events[2]["event_type"] == "failed"

        last_seen_id = all_events[1]["id"]
        incremental = await queue.get_events_since(last_event_id=last_seen_id)
        assert all(event["id"] > last_seen_id for event in incremental)
        assert any(event["event_type"] == "failed" for event in incremental)

        latest_id = await queue.get_latest_event_id()
        assert latest_id == all_events[-1]["id"]

    async def test_enqueue_stores_tenant_and_requested_user_snapshot(self, queue):
        alpha = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S01",
            payload={"prompt": "alpha"},
            script_file="episode_01.json",
            source="webui",
            tenant_id="ten_alpha",
            requested_by_user_id="camel:alice",
        )
        beta = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S01",
            payload={"prompt": "beta"},
            script_file="episode_01.json",
            source="webui",
            tenant_id="ten_beta",
            requested_by_user_id="camel:bob",
        )

        assert beta["task_id"] != alpha["task_id"]

        alpha_task = await queue.get_task(alpha["task_id"], tenant_id="ten_alpha")
        assert alpha_task is not None
        assert alpha_task["tenant_id"] == "ten_alpha"
        assert alpha_task["requested_by_user_id"] == "camel:alice"
        assert await queue.get_task(beta["task_id"], tenant_id="ten_alpha") is None

        alpha_list = await queue.list_tasks(tenant_id="ten_alpha")
        beta_list = await queue.list_tasks(tenant_id="ten_beta")
        assert alpha_list["total"] == 1
        assert beta_list["total"] == 1

    async def test_enqueue_provider_derivation_receives_tenant_and_user(self, queue, monkeypatch):
        calls = []

        async def _derive(**kwargs):
            calls.append(kwargs)
            return "ark"

        monkeypatch.setattr(generation_queue_module, "_derive_provider_id_for_enqueue", _derive)

        created = await queue.enqueue_task(
            project_name="proj-alpha",
            task_type="storyboard",
            media_type="image",
            resource_id="Alice",
            payload={"prompt": "alpha"},
            tenant_id="ten_alpha",
            requested_by_user_id="camel:alice",
        )
        claimed = await queue.claim_next_task(media_type="image")

        assert calls == [
            {
                "project_name": "proj-alpha",
                "payload": {"prompt": "alpha"},
                "task_type": "storyboard",
                "media_type": "image",
                "user_id": "camel:alice",
                "tenant_id": "ten_alpha",
            }
        ]
        assert claimed is not None
        assert claimed["task_id"] == created["task_id"]
        assert claimed["provider_id"] == "ark"

    async def test_queue_client_uses_current_identity_scope_by_default(self, queue, monkeypatch):
        monkeypatch.setattr(generation_queue_module, "get_generation_queue", lambda: queue)
        monkeypatch.setattr("lib.generation_queue_client.get_generation_queue", lambda: queue)

        async def _online(*args, **kwargs):
            return True

        monkeypatch.setattr(queue, "is_worker_online", _online)

        with current_identity_scope(user_id="camel:alice", tenant_id="ten_alpha"):
            created = await enqueue_task_only(
                project_name="proj-alpha",
                task_type="storyboard",
                media_type="image",
                resource_id="Alice",
                payload={"prompt": "alpha"},
            )

        claimed = await queue.claim_next_task(media_type="image")
        assert claimed is not None
        assert claimed["task_id"] == created["task_id"]
        assert claimed["tenant_id"] == "ten_alpha"
        assert claimed["requested_by_user_id"] == "camel:alice"

    async def test_active_task_dedupe_is_scoped_by_tenant_and_project_id(self, queue):
        first = await queue.enqueue_task(
            project_name="proj-alpha",
            task_type="character",
            media_type="image",
            resource_id="Alice",
            payload={"prompt": "alpha"},
            tenant_id="ten_team",
            requested_by_user_id="camel:alice",
        )
        same_project = await queue.enqueue_task(
            project_name="proj-alpha",
            task_type="character",
            media_type="image",
            resource_id="Alice",
            payload={"prompt": "alpha retry"},
            tenant_id="ten_team",
            requested_by_user_id="camel:alice",
        )
        other_project = await queue.enqueue_task(
            project_name="proj-beta",
            task_type="character",
            media_type="image",
            resource_id="Alice",
            payload={"prompt": "beta"},
            tenant_id="ten_team",
            requested_by_user_id="camel:alice",
        )
        other_tenant = await queue.enqueue_task(
            project_name="proj-alpha",
            task_type="character",
            media_type="image",
            resource_id="Alice",
            payload={"prompt": "other tenant"},
            tenant_id="ten_other",
            requested_by_user_id="camel:alice",
        )

        assert same_project["deduped"] is True
        assert same_project["task_id"] == first["task_id"]
        assert other_project["deduped"] is False
        assert other_project["task_id"] != first["task_id"]
        assert other_tenant["deduped"] is False
        assert other_tenant["task_id"] != first["task_id"]

    async def test_worker_lease_takeover(self, queue):
        first_ok = await queue.acquire_or_renew_worker_lease(
            name="default",
            owner_id="worker-a",
            ttl_seconds=1,
        )
        assert first_ok

        second_ok = await queue.acquire_or_renew_worker_lease(
            name="default",
            owner_id="worker-b",
            ttl_seconds=1,
        )
        assert not second_ok

        await asyncio.sleep(1.2)

        takeover_ok = await queue.acquire_or_renew_worker_lease(
            name="default",
            owner_id="worker-b",
            ttl_seconds=1,
        )
        assert takeover_ok

    async def test_claim_next_task_respects_dependencies_without_blocking_other_heads(self, queue):
        head_one = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S01",
            payload={"prompt": "p1"},
            script_file="episode_01.json",
            source="skill",
            dependency_group="episode_01.json:group:1",
            dependency_index=0,
        )
        await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S02",
            payload={"prompt": "p2"},
            script_file="episode_01.json",
            source="skill",
            dependency_task_id=head_one["task_id"],
            dependency_group="episode_01.json:group:1",
            dependency_index=1,
        )
        head_two = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S03",
            payload={"prompt": "p3"},
            script_file="episode_01.json",
            source="skill",
            dependency_group="episode_01.json:group:2",
            dependency_index=0,
        )

        first_claim = await queue.claim_next_task(media_type="image")
        second_claim = await queue.claim_next_task(media_type="image")
        blocked_claim = await queue.claim_next_task(media_type="image")

        assert first_claim is not None
        assert second_claim is not None
        assert {first_claim["task_id"], second_claim["task_id"]} == {
            head_one["task_id"],
            head_two["task_id"],
        }
        assert blocked_claim is None

        await queue.mark_task_succeeded(
            head_one["task_id"],
            {"file_path": "storyboards/scene_E1S01.png"},
        )
        unblocked_claim = await queue.claim_next_task(media_type="image")
        assert unblocked_claim is not None
        assert unblocked_claim["resource_id"] == "E1S02"

    async def test_mark_task_failed_cascades_to_queued_dependents(self, queue):
        first = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S01",
            payload={"prompt": "p1"},
            script_file="episode_01.json",
            source="skill",
            dependency_group="episode_01.json:group:1",
            dependency_index=0,
        )
        second = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S02",
            payload={"prompt": "p2"},
            script_file="episode_01.json",
            source="skill",
            dependency_task_id=first["task_id"],
            dependency_group="episode_01.json:group:1",
            dependency_index=1,
        )
        third = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S03",
            payload={"prompt": "p3"},
            script_file="episode_01.json",
            source="skill",
            dependency_task_id=second["task_id"],
            dependency_group="episode_01.json:group:1",
            dependency_index=2,
        )

        running = await queue.claim_next_task(media_type="image")
        assert running is not None
        assert running["task_id"] == first["task_id"]

        await queue.mark_task_failed(first["task_id"], "boom")

        second_task = await queue.get_task(second["task_id"])
        third_task = await queue.get_task(third["task_id"])
        assert second_task is not None
        assert third_task is not None
        assert second_task["status"] == "failed"
        assert third_task["status"] == "failed"
        assert "blocked by failed dependency" in second_task["error_message"]
        assert first["task_id"] in second_task["error_message"]
        assert second["task_id"] in third_task["error_message"]

    async def test_requeue_running_tasks(self, queue):
        task = await queue.enqueue_task(
            project_name="demo",
            task_type="video",
            media_type="video",
            resource_id="E1S01",
            payload={"prompt": "video"},
            script_file="episode_01.json",
            source="webui",
        )
        running = await queue.claim_next_task(media_type="video")
        assert running is not None
        assert running["status"] == "running"

        recovered = await queue.requeue_running_tasks()
        assert recovered == 1

        queued = await queue.get_task(task["task_id"])
        assert queued is not None
        assert queued["status"] == "queued"
        assert queued["started_at"] is None

        claimed_again = await queue.claim_next_task(media_type="video")
        assert claimed_again is not None
        assert claimed_again["task_id"] == task["task_id"]

        events = await queue.get_events_since(last_event_id=0)
        assert any(event["event_type"] == "requeued" for event in events)

    async def test_cancel_task(self, queue):
        result = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S01",
            payload={},
            script_file="ep1.json",
        )

        cancel_result = await queue.cancel_task(result["task_id"])
        assert len(cancel_result["cancelled"]) == 1
        assert cancel_result["cancelled"][0]["status"] == "cancelled"

    async def test_cancel_all_queued(self, queue):
        await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S01",
            payload={},
            script_file="ep1.json",
        )
        await queue.enqueue_task(
            project_name="demo",
            task_type="video",
            media_type="video",
            resource_id="E1S02",
            payload={},
            script_file="ep1.json",
        )

        result = await queue.cancel_all_queued("demo")
        assert result["cancelled_count"] == 2

        stats = await queue.get_task_stats(project_name="demo")
        assert stats["cancelled"] == 2
        assert stats["queued"] == 0

    async def test_persist_provider_job_id_wrapper(self, queue):
        """persist_provider_job_id 是 wrapper,只验证不抛(行为细节在 repo 层测过)。"""
        enqueued = await queue.enqueue_task(
            project_name="demo",
            task_type="video",
            media_type="video",
            resource_id="r1",
            payload={},
            script_file="ep1.json",
        )
        # 入队的 task 此时是 queued,但 persist 不校验 status(独立 commit)
        await queue.persist_provider_job_id(
            enqueued["task_id"],
            "job-abc-123",
            provider_id="ark",
            model_id="doubao-seedance-1-5-pro-251215",
        )
        task = await queue.get_task(enqueued["task_id"])
        assert task is not None
        assert task["provider_job_id"] == "job-abc-123"
        assert task["provider_id"] == "ark"
        assert task["payload"]["provider_route"] == {
            "provider_id": "ark",
            "model": "doubao-seedance-1-5-pro-251215",
        }

    async def test_persist_provider_job_id_wrapper_preserves_tenant_scope(self, queue):
        enqueued = await queue.enqueue_task(
            project_name="demo",
            task_type="video",
            media_type="video",
            resource_id="r1",
            payload={},
            script_file="ep1.json",
            tenant_id="ten_team",
            requested_by_user_id="camel:alice",
        )
        await queue.persist_provider_job_id(
            enqueued["task_id"],
            "job-tenant-123",
            tenant_id="ten_team",
            requested_by_user_id="camel:alice",
        )
        task = await queue.get_task(
            enqueued["task_id"],
            tenant_id="ten_team",
            requested_by_user_id="camel:alice",
        )
        assert task is not None
        assert task["provider_job_id"] == "job-tenant-123"

    async def test_mark_task_cancelled_wrapper(self, queue):
        """mark_task_cancelled wrapper → repo.finalize_cancelled,SQL 守卫接住 queued/cancelling/running。"""
        enqueued = await queue.enqueue_task(
            project_name="demo",
            task_type="video",
            media_type="video",
            resource_id="r1",
            payload={},
            script_file="ep1.json",
        )
        # 从 queued 直接落 cancelled(进程级 cancel 兜底路径)
        rows = await queue.mark_task_cancelled(enqueued["task_id"], cancelled_by="restart")
        assert rows == 1
        task = await queue.get_task(enqueued["task_id"])
        assert task is not None
        assert task["status"] == "cancelled"
        # 终态再调一次返回 0(SQL 守卫排除终态)
        rows = await queue.mark_task_cancelled(enqueued["task_id"])
        assert rows == 0

    async def test_cancel_task_dispatches_worker_callback(self, queue):
        """cancel_task 把 cancelling 列表派发给 worker_cancel_callback(秒级响应)。"""
        # 先把任务推到 running,这样 cancel 走 cancelling 中间态
        enqueued = await queue.enqueue_task(
            project_name="demo",
            task_type="video",
            media_type="video",
            resource_id="r1",
            payload={},
            script_file="ep1.json",
        )
        await queue.claim_next_task("video")

        signaled: list[str] = []

        def _fake_cancel(task_id: str) -> bool:
            signaled.append(task_id)
            return True

        queue.set_worker_cancel_callback(_fake_cancel)
        result = await queue.cancel_task(enqueued["task_id"])
        # running task 应进入 cancelling
        assert signaled == [enqueued["task_id"]]
        assert result["cancelling"] == [enqueued["task_id"]]

    async def test_finalize_cancelled_dispatches_cascade_callback(self, queue):
        """mark_task_cancelled(finalize 入口) 把级联出的 running 子任务派发给 callback。

        A(running)→B(running)→C(queued)：worker finally 调 finalize_cancelled(A)，
        cascade 把 B 标 cancelling，须同步调 callback(B) 让 worker request_cancel(B)
        立刻发 in-process cancel，而非等 B 跑完 provider 调用。
        """
        from sqlalchemy import update as sql_update

        from lib.db.models.task import Task

        a_task = await queue.enqueue_task(
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S01",
            payload={},
            script_file="ep1.json",
        )
        b_task = await queue.enqueue_task(
            project_name="demo",
            task_type="video",
            media_type="video",
            resource_id="E1S01",
            payload={},
            script_file="ep1.json",
            dependency_task_id=a_task["task_id"],
        )

        # 把 A 拉到 running、B 也直接 set 成 running（跳过 dep 守卫）
        await queue.claim_next_task("image")
        async with queue._session_factory() as session:
            await session.execute(sql_update(Task).where(Task.task_id == b_task["task_id"]).values(status="running"))
            await session.commit()

        signaled: list[str] = []

        def _fake_cancel(task_id: str) -> bool:
            signaled.append(task_id)
            return True

        queue.set_worker_cancel_callback(_fake_cancel)
        # finalize_cancelled(A) 级联：A → cancelled、B(running) → cancelling
        rows = await queue.mark_task_cancelled(a_task["task_id"], cancelled_by="user")
        assert rows == 1
        # B 必须被分发 callback —— Repository 返回意图、Queue 上层分发
        assert b_task["task_id"] in signaled

    async def test_cancel_task_callback_exception_does_not_break(self, queue):
        """callback 抛异常不影响 cancel_task 返回(best-effort 信号)。"""
        enqueued = await queue.enqueue_task(
            project_name="demo",
            task_type="video",
            media_type="video",
            resource_id="r1",
            payload={},
            script_file="ep1.json",
        )
        await queue.claim_next_task("video")

        def _bad_cancel(_task_id: str) -> bool:
            raise RuntimeError("worker not responding")

        queue.set_worker_cancel_callback(_bad_cancel)
        # 不应抛
        result = await queue.cancel_task(enqueued["task_id"])
        assert result["cancelling"] == [enqueued["task_id"]]

    async def test_get_cancel_preview_wrapper(self, queue):
        """get_cancel_preview wrapper → repo.get_cancel_preview。"""
        enqueued = await queue.enqueue_task(
            project_name="demo",
            task_type="video",
            media_type="video",
            resource_id="r1",
            payload={},
            script_file="ep1.json",
        )
        preview = await queue.get_cancel_preview(enqueued["task_id"])
        assert preview["task"]["task_id"] == enqueued["task_id"]
