from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth import CurrentUserInfo, get_current_user
from server.routers import api_keys


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
