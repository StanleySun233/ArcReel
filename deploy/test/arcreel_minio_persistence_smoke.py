from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

import arcreel_tenant_role_minio_smoke as smoke

API_BASE = os.environ["ARCREEL_API_BASE_URL"].rstrip("/")
TOKEN_SECRET = os.environ["ARCREEL_TOKEN_SECRET"]
MINIO_PUBLIC_ENDPOINT = os.environ.get("ARCREEL_MINIO_PUBLIC_ENDPOINT", "http://127.0.0.1:19000").rstrip("/")
MINIO_BUCKET = os.environ.get("ARCREEL_MINIO_BUCKET", "arcreel-files")
PG_CONTAINER = os.environ.get("ARCREEL_POSTGRES_CONTAINER", "arcreel-dev-postgres-1")
PG_USER = os.environ.get("ARCREEL_POSTGRES_USER", "arcreel")
PG_DB = os.environ.get("ARCREEL_POSTGRES_DB", "arcreel_acceptance_20260710220207")


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def file_token(file_id: str, user_id: str, tenant_id: str | None, exp: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload: dict[str, Any] = {
        "purpose": "file_access",
        "file_id": file_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "iat": exp - 10,
        "exp": exp,
    }
    signing_input = ".".join(
        [
            b64url(json.dumps(header, separators=(",", ":")).encode()),
            b64url(json.dumps(payload, separators=(",", ":")).encode()),
        ]
    )
    signature = hmac.new(TOKEN_SECRET.encode(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{b64url(signature)}"


def query_object_key(file_id: str) -> str:
    escaped_file_id = file_id.replace("'", "''")
    sql = f"select object_key from files where id = '{escaped_file_id}'"
    result = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB, "-tAc", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return smoke.require_str(result.stdout.strip(), f"object key missing for {file_id}")


def direct_minio_get(object_key: str) -> int:
    url = f"{MINIO_PUBLIC_ENDPOINT}/{MINIO_BUCKET}/{urllib.parse.quote(object_key, safe='/')}"
    status, _payload, _headers = smoke.request_url("GET", url)
    return status


def read_signed(token: str, file_id: str) -> str:
    status, payload, _ = smoke.request("GET", f"/api/v1/files/{file_id}/signed-url", token=token)
    smoke.expect(status == 200, f"signed-url returned {status}: {payload!r}")
    smoke.expect(payload.get("expires_in") == 300, f"expires_in mismatch: {payload!r}")
    url = smoke.require_str(payload.get("url"), f"signed url missing: {payload!r}")
    smoke.expect(file_id in url and "token=" in url, f"signed url shape mismatch: {url}")
    status, body, _ = smoke.request_url("GET", url)
    smoke.expect(status == 200, f"signed content returned {status}: {body!r}")
    return smoke.raw_text(body)


def seed(state_file: Path) -> None:
    smoke.ensure_camel_root()
    run_id = os.environ.get("SMOKE_RUN_ID") or uuid.uuid4().hex[:8]
    owner = smoke.login_user("po", run_id)
    viewer = smoke.login_user("pv", run_id)
    status, payload, _ = smoke.request(
        "POST", "/api/v1/tenants", token=owner["token"], body={"name": f"Persist {run_id}"}
    )
    smoke.expect(status == 200, f"tenant create returned {status}: {payload!r}")
    tenant_id = smoke.require_str(payload.get("id"), f"tenant id missing: {payload!r}")
    owner_team = smoke.tenant_token(owner["token"], tenant_id)
    smoke.add_member(owner_team, viewer["user_id"], "view")
    viewer_team = smoke.tenant_token(viewer["token"], tenant_id)
    project_name = f"persist-{run_id}"
    smoke.create_project(owner_team, project_name, f"Persist {run_id}")
    smoke.put_source(owner_team, project_name)
    uploaded = smoke.upload_private_file(owner_team, "private-proof.txt", b"private persistence proof")
    file_id = smoke.require_str(uploaded.get("file_id"), f"file id missing: {uploaded!r}")
    object_key = query_object_key(file_id)

    smoke.expect(direct_minio_get(object_key) in (401, 403), f"direct minio url was public for {object_key}")
    smoke.expect(read_signed(owner_team, file_id) == "private persistence proof", "owner signed content mismatch")
    smoke.expect(read_signed(viewer_team, file_id) == "private persistence proof", "viewer signed content mismatch")
    expired = file_token(file_id, viewer["user_id"], tenant_id, int(time.time()) - 10)
    status, payload, _ = smoke.request_url("GET", f"{API_BASE}/api/v1/files/{file_id}/content?token={expired}")
    smoke.expect(status == 403, f"expired file token returned {status}: {payload!r}")

    state_file.write_text(
        json.dumps(
            {
                "owner_team": owner_team,
                "viewer_team": viewer_team,
                "tenant_id": tenant_id,
                "project_name": project_name,
                "file_id": file_id,
                "object_key": object_key,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "phase": "seed", "state_file": str(state_file)}, ensure_ascii=False))


def verify(state_file: Path) -> None:
    state = json.loads(state_file.read_text(encoding="utf-8"))
    status, payload, _ = smoke.request("GET", "/api/v1/projects", token=state["owner_team"])
    smoke.expect(status == 200, f"projects after restart returned {status}: {payload!r}")
    names = {item.get("name") for item in payload.get("projects") or []}
    smoke.expect(state["project_name"] in names, f"project missing after restart: {payload!r}")
    smoke.expect(direct_minio_get(state["object_key"]) in (401, 403), "direct minio url became public after restart")
    smoke.expect(
        read_signed(state["viewer_team"], state["file_id"]) == "private persistence proof", "file missing after restart"
    )
    print(
        json.dumps(
            {
                "ok": True,
                "phase": "verify",
                "checks": [
                    "minio direct object url is private",
                    "backend signed file url returns content",
                    "expired file access token is rejected",
                    "project and file remain readable after app restart",
                ],
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["seed", "verify"], required=True)
    parser.add_argument("--state-file", required=True)
    args = parser.parse_args()
    path = Path(args.state_file)
    if args.phase == "seed":
        seed(path)
    else:
        verify(path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
