from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth import CurrentUserInfo, get_current_user
from server.routers import api_keys
from server.services.tenant_auth import TenantAccess


def _make_client() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUserInfo(
        id="usr_1",
        sub="user",
        role="admin",
        tenant_id="ten_1",
        tenant_role="admin",
    )
    app.include_router(api_keys.router, prefix="/api/v1")
    return TestClient(app)


def test_issued_tokens_endpoints_are_disabled():
    with _make_client() as client:
        responses = [
            client.get("/api/v1/api-keys"),
            client.post("/api/v1/api-keys", json={"name": "token"}),
            client.patch("/api/v1/api-keys/1", json={"name": "token"}),
            client.delete("/api/v1/api-keys/1"),
        ]

    assert [resp.status_code for resp in responses] == [403, 403, 403, 403]
    assert [resp.json()["detail"] for resp in responses] == ["feature_disabled"] * 4


def test_update_api_key_business_path_is_retained_when_enabled(monkeypatch):
    calls = []

    class _Begin:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

    class _Session:
        def begin(self):
            return _Begin()

    class _SessionContext:
        async def __aenter__(self):
            return _Session()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

    class _Repo:
        def __init__(self, session, *, user_id, tenant_id):
            calls.append(("repo", user_id, tenant_id))

        async def get_by_id(self, key_id):
            calls.append(("get", key_id))
            return {
                "id": key_id,
                "name": "old",
                "key_prefix": "arc-ten_1-old",
                "created_at": "2026-07-11T00:00:00Z",
                "expires_at": None,
                "last_used_at": None,
                "key_hash": "hash_1",
            }

        async def update(self, key_id, *, name, expires_at):
            calls.append(("update", key_id, name, expires_at))
            return {
                "id": key_id,
                "name": name,
                "key_prefix": "arc-ten_1-old",
                "created_at": "2026-07-11T00:00:00Z",
                "expires_at": None,
                "last_used_at": None,
            }

    async def _access(session, user, *, minimum_role):
        calls.append(("access", user.id, minimum_role))
        return TenantAccess(id="ten_1", name="Tenant", role="admin", is_owner=True, personal=True)

    async def _set_context(session, *, user_id, tenant_id):
        calls.append(("context", user_id, tenant_id))

    def _invalidate(key_hash):
        calls.append(("invalidate", key_hash))

    monkeypatch.setattr(api_keys, "ISSUED_TOKENS_ENABLED", True)
    monkeypatch.setattr(api_keys, "async_session_factory", lambda: _SessionContext())
    monkeypatch.setattr(api_keys, "ApiKeyRepository", _Repo)
    monkeypatch.setattr(api_keys, "require_tenant_access", _access)
    monkeypatch.setattr(api_keys, "set_tenant_context", _set_context)
    monkeypatch.setattr(api_keys, "invalidate_api_key_cache", _invalidate)

    with _make_client() as client:
        resp = client.patch("/api/v1/api-keys/7", json={"name": "renamed", "expires_days": 0})

    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed"
    assert ("access", "usr_1", "admin") in calls
    assert ("context", "usr_1", "ten_1") in calls
    assert ("repo", "usr_1", "ten_1") in calls
    assert ("get", 7) in calls
    assert ("invalidate", "hash_1") in calls
    assert ("update", 7, "renamed", None) in calls
