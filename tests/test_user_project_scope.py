from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib import app_data_dir as app_data_dir_module
from lib.app_data_dir import app_data_dir
from lib.db.repositories.project_repo import ProjectRow
from lib.project_manager import ProjectManager
from lib.status_calculator import StatusCalculator
from server import auth as auth_module
from server.routers import files, projects
from server.services.tenant_auth import TenantAccess


class _ProjectRepository:
    rows: dict[tuple[str, str], ProjectRow] = {}

    def __init__(self, _session, *, tenant_id: str):
        self.tenant_id = tenant_id

    async def create(self, *, project_id: str, name: str, created_by_user_id: str, local_path: str):
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        row = ProjectRow(
            id=project_id,
            tenant_id=self.tenant_id,
            name=name,
            created_by_user_id=created_by_user_id,
            local_path=local_path,
            created_at=now,
            updated_at=now,
        )
        self.rows[(self.tenant_id, project_id)] = row
        return row

    async def get_by_name(self, name: str):
        for (tenant_id, _project_id), row in self.rows.items():
            if tenant_id == self.tenant_id and row.name == name:
                return row
        return None

    async def get_by_id(self, project_id: str):
        return self.rows.get((self.tenant_id, project_id))

    async def list_all(self):
        return [row for (tenant_id, _project_id), row in self.rows.items() if tenant_id == self.tenant_id]


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
    monkeypatch.setattr(projects, "ProjectRepository", _ProjectRepository)

    async def _tenant_access(_session, current_user, **_kwargs):
        tenant_id = current_user.tenant_id
        return TenantAccess(id=tenant_id, name=tenant_id, role="admin", is_owner=True, personal=True)

    monkeypatch.setattr(projects, "require_tenant_access", _tenant_access)
    monkeypatch.setattr(files, "require_tenant_access", _tenant_access)

    app = FastAPI()
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(files.router, prefix="/api/v1")
    return TestClient(app)


def _headers(camel_user_id: str) -> dict[str, str]:
    token = auth_module.create_token(
        f"user-{camel_user_id}",
        user_id=f"camel:{camel_user_id}",
        provider="camel",
        tenant_id=f"ten_{camel_user_id}",
        tenant_role="admin",
    )
    return {"Authorization": f"Bearer {token}"}


def test_project_and_file_routes_are_scoped_by_current_user(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _ProjectRepository.rows = {}
    alice = _headers("alice")
    bob = _headers("bob")

    with client:
        create_alice = client.post(
            "/api/v1/projects",
            json={"name": "shared", "title": "Alice Project"},
            headers=alice,
        )
        assert create_alice.status_code == 200
        alice_project_id = create_alice.json()["id"]

        create_bob = client.post(
            "/api/v1/projects",
            json={"name": "shared", "title": "Bob Project"},
            headers=bob,
        )
        assert create_bob.status_code == 200
        bob_project_id = create_bob.json()["id"]

        alice_projects = client.get("/api/v1/projects", headers=alice)
        bob_projects = client.get("/api/v1/projects", headers=bob)
        assert alice_projects.status_code == 200
        assert bob_projects.status_code == 200
        assert alice_projects.json()["projects"][0]["title"] == "Alice Project"
        assert bob_projects.json()["projects"][0]["title"] == "Bob Project"

        alice_project = client.get(f"/api/v1/projects/{alice_project_id}", headers=alice)
        bob_project = client.get(f"/api/v1/projects/{bob_project_id}", headers=bob)
        assert alice_project.json()["project"]["title"] == "Alice Project"
        assert bob_project.json()["project"]["title"] == "Bob Project"

        upload = client.post(
            f"/api/v1/projects/{alice_project_id}/upload/source",
            files={"file": ("chapter.txt", "alice-only", "text/plain")},
            headers=alice,
        )
        assert upload.status_code == 200

        alice_file = client.get(f"/api/v1/files/{alice_project_id}/source/chapter.txt", headers=alice)
        bob_file = client.get(f"/api/v1/files/{alice_project_id}/source/chapter.txt", headers=bob)
        anonymous_file = client.get(f"/api/v1/files/{alice_project_id}/source/chapter.txt")
        assert alice_file.status_code == 200
        assert alice_file.text == "alice-only"
        assert bob_file.status_code == 404
        assert anonymous_file.status_code == 401
