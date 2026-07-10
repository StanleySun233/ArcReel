from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

API_BASE = os.environ["ARCREEL_API_BASE_URL"].rstrip("/")
PNG_1X1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/l4Q9WQAAAABJRU5ErkJggg=="


class SetupFailure(RuntimeError):
    pass


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SetupFailure(message)


def request(
    method: str,
    path: str,
    token: str,
    *,
    body: dict[str, Any] | None = None,
    raw: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    merged = dict(headers or {})
    merged["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        merged["Content-Type"] = "application/json"
    if raw is not None:
        data = raw
    req = urllib.request.Request(API_BASE + path, data=data, headers=merged, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            response_body = response.read()
            return response.status, json.loads(response_body.decode("utf-8")) if response_body else {}
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(response_body)
        except json.JSONDecodeError:
            payload = {"raw": response_body}
        return exc.code, payload


def upload_png(token: str) -> str:
    boundary = f"----arcreel-ui-{uuid.uuid4().hex}"
    payload = base64.b64decode(PNG_1X1)
    raw = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="ui-proof.png"\r\n',
            b"Content-Type: image/png\r\n\r\n",
            payload,
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="purpose"\r\n\r\nui-acceptance\r\n',
            f"--{boundary}--\r\n".encode(),
        ]
    )
    status, body = request(
        "POST",
        "/api/v1/files",
        token,
        raw=raw,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    expect(status == 200, f"upload png returned {status}: {body!r}")
    file_id = body.get("file_id")
    expect(isinstance(file_id, str) and file_id.startswith("fil_"), f"file id missing: {body!r}")
    return file_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-state", required=True)
    parser.add_argument("--output-state", required=True)
    args = parser.parse_args()

    state = json.loads(Path(args.input_state).read_text(encoding="utf-8"))
    owner_token = state["owner_team"]
    file_id = upload_png(owner_token)
    suffix = uuid.uuid4().hex[:6]
    name = f"UI Asset {suffix}"

    status, body = request(
        "POST",
        "/api/v1/assets",
        owner_token,
        body={
            "library": "tenant",
            "type": "character",
            "name": name,
            "description": "before sync",
            "image_file_id": file_id,
        },
    )
    expect(status == 200, f"create tenant asset returned {status}: {body!r}")
    tenant_binding = body["asset"]["binding_id"]

    status, body = request(
        "POST",
        "/api/v1/assets/import",
        owner_token,
        body={"source_binding_id": tenant_binding, "target_library": "personal"},
    )
    expect(status == 200, f"import asset returned {status}: {body!r}")
    personal_binding = body["asset"]["binding_id"]

    synced_name = f"{name} Synced"
    status, body = request(
        "PATCH",
        f"/api/v1/assets/{tenant_binding}",
        owner_token,
        body={"name": synced_name, "description": "after sync"},
    )
    expect(status == 200, f"update tenant asset returned {status}: {body!r}")

    output = {
        **state,
        "ui_file_id": file_id,
        "tenant_asset_binding": tenant_binding,
        "personal_asset_binding": personal_binding,
        "ui_asset_name": name,
        "ui_asset_synced_name": synced_name,
    }
    Path(args.output_state).write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "state_file": args.output_state, "asset": name}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
