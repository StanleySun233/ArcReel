from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

import asyncpg
import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from deploy.test.arcreel_tenant_role_minio_smoke import (
    API_BASE,
    SmokeFailure,
    ensure_camel_root,
    expect,
    login_user,
    raw_text,
    request,
    request_url,
    require_str,
    upload_private_file,
)

TOKEN_SECRET = os.environ["ARCREEL_TOKEN_SECRET"]
MINIO_PUBLIC_ENDPOINT = os.environ.get("ARCREEL_MINIO_PUBLIC_ENDPOINT", "http://127.0.0.1:19000").rstrip("/")
MINIO_BUCKET = os.environ.get("ARCREEL_MINIO_BUCKET", "arcreel-files")


def database_url() -> str:
    value = os.environ.get("ARCREEL_TEST_DATABASE_ADMIN_URL") or os.environ.get("DATABASE_URL") or ""
    if not value:
        raise SmokeFailure("database URL is not configured")
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


async def object_key_for_file(file_id: str) -> str:
    connection = await asyncpg.connect(database_url())
    try:
        row = await connection.fetchrow("select object_key from files where id = $1", file_id)
    finally:
        await connection.close()
    if row is None:
        raise SmokeFailure(f"file row not found: {file_id}")
    return str(row["object_key"])


def tenant_id_for_token(token: str) -> str:
    status, payload, _ = request("GET", "/api/v1/auth/tenants", token=token)
    expect(status == 200, f"tenant list returned {status}: {payload!r}")
    tenants = payload.get("tenants")
    expect(isinstance(tenants, list) and bool(tenants), f"tenant list missing: {payload!r}")
    tenant_id = tenants[0].get("id") if isinstance(tenants[0], dict) else None
    return require_str(tenant_id, f"tenant id missing: {payload!r}")


def file_access_token(file_id: str, user_id: str, tenant_id: str, *, expires_at: float) -> str:
    return jwt.encode(
        {
            "purpose": "file_access",
            "file_id": file_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "iat": expires_at - 60,
            "exp": expires_at,
        },
        TOKEN_SECRET,
        algorithm="HS256",
    )


def signed_file_url(token: str, file_id: str) -> tuple[str, int]:
    status, payload, _ = request("GET", f"/api/v1/files/{file_id}/signed-url", token=token)
    expect(status == 200, f"signed-url returned {status}: {payload!r}")
    return require_str(payload.get("url"), f"signed-url missing: {payload!r}"), int(payload.get("expires_in") or 0)


def direct_minio_url(object_key: str) -> str:
    return f"{MINIO_PUBLIC_ENDPOINT}/{MINIO_BUCKET}/{urllib.parse.quote(object_key, safe='/')}"


def main() -> None:
    ensure_camel_root()
    run_id = os.environ.get("SMOKE_RUN_ID") or f"minio-{os.getpid()}"
    user = login_user("minio", run_id)
    tenant_id = tenant_id_for_token(user["token"])
    uploaded = upload_private_file(user["token"], "proof.txt", b"minio security proof")
    file_id = require_str(uploaded.get("file_id"), f"file id missing: {uploaded!r}")
    object_key = asyncio.run(object_key_for_file(file_id))

    status, payload, _ = request_url("GET", direct_minio_url(object_key))
    expect(status in (401, 403), f"direct minio object returned {status}: {payload!r}")

    signed_url, expires_in = signed_file_url(user["token"], file_id)
    expect(expires_in == 300, f"signed url ttl mismatch: {expires_in}")
    status, payload, _ = request_url("GET", signed_url)
    expect(
        status == 200 and raw_text(payload) == "minio security proof", f"signed content failed: {status} {payload!r}"
    )

    status, payload, _ = request_url("GET", signed_url + "x")
    expect(status == 403, f"tampered signed url returned {status}: {payload!r}")

    expired = file_access_token(file_id, user["user_id"], tenant_id, expires_at=time.time() - 10)
    status, payload, _ = request_url("GET", f"{API_BASE}/api/v1/files/{file_id}/content?token={expired}")
    expect(status == 403, f"expired signed token returned {status}: {payload!r}")

    print(
        json.dumps(
            {
                "ok": True,
                "checks": [
                    "private minio bucket rejects direct object access",
                    "backend signed file URL reads minio object",
                    "signed file URL keeps 300 second TTL contract",
                    "tampered and expired signed tokens are rejected",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
