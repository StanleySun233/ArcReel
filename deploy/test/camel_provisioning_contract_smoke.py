from __future__ import annotations

import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from deploy.test.arcreel_tenant_role_minio_smoke import (
    API_BASE,
    CAMEL_API_BASE,
    authorize_with_camel,
    camel_login,
    ensure_camel_root,
    expect,
    login_user,
    make_opener,
    request,
    request_url,
    require_str,
)

CLIENT_ID = os.environ.get("CAMEL_OAUTH_CLIENT_ID", "arc-test-client")
CLIENT_SECRET = os.environ.get("CAMEL_OAUTH_CLIENT_SECRET", "arc-test-secret")


def parse_query(url: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)


def form_request(url: str, body: dict[str, str]) -> tuple[int, dict, dict[str, str]]:
    raw = urllib.parse.urlencode(body).encode("utf-8")
    return request_url(
        "POST",
        url,
        raw=raw,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def token_from_authorization_url(camel_auth: dict, authorization_url: str) -> str:
    callback_location = authorize_with_camel(camel_auth, authorization_url)
    callback_query = parse_query(callback_location)
    authorization_query = parse_query(authorization_url)
    code = require_str((callback_query.get("code") or [""])[0], f"OAuth code missing: {callback_location}")
    redirect_uri = require_str(
        (authorization_query.get("redirect_uri") or [""])[0],
        f"redirect_uri missing: {authorization_url}",
    )
    status, payload, _ = form_request(
        f"{CAMEL_API_BASE}/api/oauth/provider/token",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    expect(status == 200, f"token exchange returned {status}: {payload!r}")
    return require_str(payload.get("access_token"), f"access token missing: {payload!r}")


def bootstrap_authorization_url(arcreel_token: str, mode: str = "create") -> str:
    status, payload, _ = request("POST", f"/api/v1/camel/bootstrap/start-url?mode={mode}", token=arcreel_token)
    expect(status == 200, f"bootstrap start-url returned {status}: {payload!r}")
    return require_str(payload.get("authorization_url"), f"authorization url missing: {payload!r}")


def login_authorization_url() -> str:
    opener = make_opener(no_redirect=True)
    status, payload, headers = request_url(
        "GET", f"{API_BASE}/api/v1/auth/camel/start?from=/app/projects", opener=opener
    )
    expect(status in (302, 303, 307), f"login start returned {status}: {payload!r}")
    return require_str(headers.get("Location") or headers.get("location"), f"login location missing: {headers!r}")


def provision(access_token: str, body: dict) -> tuple[int, dict]:
    status, payload, _ = request_url(
        "POST",
        f"{CAMEL_API_BASE}/api/oauth/provider/arcreel-tokens",
        body=body,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return status, payload


def expect_token_success(payload: dict) -> None:
    expect(payload.get("success") is True, f"provisioning failed: {payload!r}")
    tokens = payload.get("tokens")
    expect(isinstance(tokens, list), f"tokens missing: {payload!r}")
    medias = {item.get("media") for item in tokens if isinstance(item, dict)}
    expect(medias == {"image", "text", "video", "audio"}, f"token media mismatch: {payload!r}")


def main() -> None:
    ensure_camel_root()
    run_id = os.environ.get("SMOKE_RUN_ID") or os.urandom(4).hex()
    username = f"prov-{run_id}"
    user = login_user("prov", run_id)
    camel_auth = camel_login(username, "ArcReel1234")

    status, payload, _ = request_url(
        "POST",
        f"{CAMEL_API_BASE}/api/oauth/provider/arcreel-tokens",
        body={"client": "arcreel", "mode": "create", "idempotency_key": f"{run_id}-no-auth", "dry_run": False},
    )
    expect(status == 401 and payload.get("success") is False, f"no-auth returned {status}: {payload!r}")

    login_scope_token = token_from_authorization_url(camel_auth, login_authorization_url())
    status, payload = provision(
        login_scope_token,
        {"client": "arcreel", "mode": "create", "idempotency_key": f"{run_id}-missing-scope", "dry_run": False},
    )
    expect(status in (401, 403) and payload.get("success") is False, f"missing-scope returned {status}: {payload!r}")

    bootstrap_token = token_from_authorization_url(camel_auth, bootstrap_authorization_url(user["token"]))
    status, payload = provision(
        bootstrap_token,
        {"client": "other-client", "mode": "create", "idempotency_key": f"{run_id}-wrong-client", "dry_run": False},
    )
    expect(status in (400, 403) and payload.get("success") is False, f"wrong-client returned {status}: {payload!r}")

    create_body = {"client": "arcreel", "mode": "create", "idempotency_key": f"{run_id}-create", "dry_run": False}
    status, first = provision(bootstrap_token, create_body)
    expect(status == 200, f"first create returned {status}: {first!r}")
    expect_token_success(first)
    status, second = provision(bootstrap_token, create_body)
    expect(
        status == 200 and second.get("error") == "token_name_conflict", f"retry create returned {status}: {second!r}"
    )

    status, conflict = provision(
        bootstrap_token,
        {"client": "arcreel", "mode": "create", "idempotency_key": f"{run_id}-conflict", "dry_run": False},
    )
    expect(
        status == 200 and conflict.get("error") == "token_name_conflict", f"conflict returned {status}: {conflict!r}"
    )

    repair_token = token_from_authorization_url(camel_auth, bootstrap_authorization_url(user["token"], mode="repair"))
    status, repaired = provision(
        repair_token,
        {"client": "arcreel", "mode": "repair", "idempotency_key": f"{run_id}-repair", "dry_run": False},
    )
    expect(status == 200, f"repair returned {status}: {repaired!r}")
    expect_token_success(repaired)

    print(
        json.dumps(
            {
                "ok": True,
                "checks": [
                    "provisioning rejects missing bearer token",
                    "provisioning rejects login-scope token without token-provision scope",
                    "provisioning rejects wrong client value",
                    "provisioning repeated create returns explicit token conflict",
                    "provisioning create reports token conflict for a new key",
                    "provisioning repair recreates managed media tokens",
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
