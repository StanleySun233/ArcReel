from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib import app_data_dir as app_data_dir_module
from lib.app_data_dir import app_data_dir
from lib.project_manager import ProjectManager
from lib.status_calculator import StatusCalculator
from server import auth as auth_module
from server.routers import files, projects


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "scope-test-secret-32-bytes-long-value")
    monkeypatch.setenv("ARCREEL_DATA_DIR", str(tmp_path / "data"))
    app_data_dir_module._reset_for_tests()
    auth_module._cached_token_secret = None

    pm = ProjectManager(app_data_dir())
    monkeypatch.setattr(projects, "pm", pm)
    monkeypatch.setattr(projects, "calc", StatusCalculator(pm))
    monkeypatch.setattr(files, "pm", pm)

    app = FastAPI()
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(files.router, prefix="/api/v1")
    return TestClient(app)


def _headers(camel_user_id: str) -> dict[str, str]:
    token = auth_module.create_token(
        f"user-{camel_user_id}",
        user_id=f"camel:{camel_user_id}",
        provider="camel",
    )
    return {"Authorization": f"Bearer {token}"}


def test_project_and_file_routes_are_scoped_by_current_user(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    alice = _headers("alice")
    bob = _headers("bob")

    with client:
        create_alice = client.post(
            "/api/v1/projects",
            json={"name": "shared", "title": "Alice Project"},
            headers=alice,
        )
        assert create_alice.status_code == 200

        create_bob = client.post(
            "/api/v1/projects",
            json={"name": "shared", "title": "Bob Project"},
            headers=bob,
        )
        assert create_bob.status_code == 200

        alice_projects = client.get("/api/v1/projects", headers=alice)
        bob_projects = client.get("/api/v1/projects", headers=bob)
        assert alice_projects.status_code == 200
        assert bob_projects.status_code == 200
        assert alice_projects.json()["projects"][0]["title"] == "Alice Project"
        assert bob_projects.json()["projects"][0]["title"] == "Bob Project"

        alice_project = client.get("/api/v1/projects/shared", headers=alice)
        bob_project = client.get("/api/v1/projects/shared", headers=bob)
        assert alice_project.json()["project"]["title"] == "Alice Project"
        assert bob_project.json()["project"]["title"] == "Bob Project"

        upload = client.post(
            "/api/v1/projects/shared/upload/source",
            files={"file": ("chapter.txt", "alice-only", "text/plain")},
            headers=alice,
        )
        assert upload.status_code == 200

        alice_file = client.get("/api/v1/files/shared/source/chapter.txt", headers=alice)
        bob_file = client.get("/api/v1/files/shared/source/chapter.txt", headers=bob)
        anonymous_file = client.get("/api/v1/files/shared/source/chapter.txt")
        assert alice_file.status_code == 200
        assert alice_file.text == "alice-only"
        assert bob_file.status_code == 404
        assert anonymous_file.status_code == 401
