from __future__ import annotations

import base64
import hashlib
import hmac
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

API_BASE = os.environ["ARCREEL_API_BASE_URL"].rstrip("/")
TOKEN_SECRET = os.environ["ARCREEL_TOKEN_SECRET"]
EXPECTED_PROVIDER_BASE_URL = os.environ["ARCREEL_EXPECTED_PROVIDER_BASE_URL"]
CAMEL_API_BASE = os.environ.get("CAMEL_API_BASE_URL", "").rstrip("/")
CAMEL_ROOT_USERNAME = os.environ.get("CAMEL_ROOT_USERNAME", "root")
CAMEL_ROOT_PASSWORD = os.environ.get("CAMEL_ROOT_PASSWORD", "test-root-password")
ARCREEL_REDIRECT_URI = os.environ.get(
    "ARCREEL_REDIRECT_URI",
    "http://localhost:11241/api/v1/auth/camel/callback",
)
JsonObject = dict[str, Any]


class SmokeFailure(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    handler_order = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

    def http_error_302(self, req, fp, code, msg, headers):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def camel_jwt(camel_user_id: str = "test-user") -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": "test-user",
        "user_id": f"camel:{camel_user_id}",
        "provider": "camel",
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = ".".join(
        [
            b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(TOKEN_SECRET.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return signing_input + "." + b64url(signature)


def request_url(
    method: str,
    url: str,
    *,
    body: dict | None = None,
    headers: dict | None = None,
    form: dict | None = None,
    raw: bytes | str | None = None,
    opener=None,
) -> tuple[int, JsonObject, dict[str, str]]:
    data = None
    req_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        req_headers["Content-Type"] = "application/x-www-form-urlencoded"
    if raw is not None:
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        open_fn = opener.open if opener is not None else urllib.request.urlopen
        with open_fn(req, timeout=20) as response:
            response_body = response.read()
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return response.status, json.loads(response_body.decode("utf-8")), dict(response.headers)
            return response.status, {"raw": response_body.decode("utf-8", errors="replace")}, dict(response.headers)
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError:
            parsed = {"raw": response_body}
        return exc.code, parsed, dict(exc.headers)


def request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    headers: dict | None = None,
    form: dict | None = None,
    raw: bytes | str | None = None,
) -> tuple[int, JsonObject, dict[str, str]]:
    return request_url(method, API_BASE + path, body=body, headers=headers, form=form, raw=raw)


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def bearer(token: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token or camel_jwt()}"}


def cookie_header(headers: dict) -> str:
    raw = headers.get("Set-Cookie") or headers.get("set-cookie") or ""
    return raw.split(";", 1)[0] if raw else ""


def make_opener(*, no_redirect: bool = False, jar: http.cookiejar.CookieJar | None = None):
    cookie_jar = jar or http.cookiejar.CookieJar()
    handlers: list[urllib.request.BaseHandler] = [urllib.request.HTTPCookieProcessor(cookie_jar)]
    if no_redirect:
        handlers.append(NoRedirect())
    return urllib.request.build_opener(*handlers)


def rewrite_base(url: str, base_url: str) -> str:
    old = urllib.parse.urlsplit(url)
    base = urllib.parse.urlsplit(base_url)
    return urllib.parse.urlunsplit((base.scheme, base.netloc, old.path, old.query, old.fragment))


def with_query(url: str, **params: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    query.update(params)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), parts.fragment)
    )


def parse_redirect(location: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    parts = urllib.parse.urlsplit(location)
    return urllib.parse.parse_qs(parts.query), urllib.parse.parse_qs(parts.fragment)


def expect_success_payload(payload: JsonObject, label: str) -> None:
    expect(payload.get("success") is True, f"{label}: success was not true: {payload!r}")


def raw_text(payload: JsonObject) -> str:
    value = payload.get("raw")
    return value if isinstance(value, str) else ""


def require_str(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value:
        raise SmokeFailure(message)
    return value


def require_object(value: Any, message: str) -> JsonObject:
    if not isinstance(value, dict):
        raise SmokeFailure(message)
    return value


def ensure_camel_root() -> None:
    if not CAMEL_API_BASE:
        raise SmokeFailure("CAMEL_API_BASE_URL is not configured")
    status, payload, _ = request_url("GET", f"{CAMEL_API_BASE}/api/setup")
    expect(status == 200, f"GET /api/setup returned {status}")
    expect_success_payload(payload, "GET /api/setup")
    data = payload.get("data") or {}
    if data.get("status") is True:
        return
    status, payload, _ = request_url(
        "POST",
        f"{CAMEL_API_BASE}/api/setup",
        body={
            "username": CAMEL_ROOT_USERNAME,
            "password": CAMEL_ROOT_PASSWORD,
            "confirmPassword": CAMEL_ROOT_PASSWORD,
            "SelfUseModeEnabled": False,
            "DemoSiteEnabled": False,
        },
    )
    expect(status == 200, f"POST /api/setup returned {status}")
    expect_success_payload(payload, "POST /api/setup")


def camel_login(username: str, password: str):
    jar = http.cookiejar.CookieJar()
    opener = make_opener(jar=jar)
    status, payload, _ = request_url(
        "POST",
        f"{CAMEL_API_BASE}/api/user/register",
        body={"username": username, "password": password},
        opener=opener,
    )
    if status != 200 or payload.get("success") is not True:
        message = json.dumps(payload, ensure_ascii=False)
        expect(
            "exist" in message.lower() or "已存在" in message,
            f"POST /api/user/register returned {status}: {payload!r}",
        )
    status, payload, headers = request_url(
        "POST",
        f"{CAMEL_API_BASE}/api/user/login",
        body={"username": username, "password": password},
        opener=opener,
    )
    expect(status == 200, f"POST /api/user/login returned {status}")
    expect_success_payload(payload, "POST /api/user/login")
    return {"jar": jar, "cookie": cookie_header(headers)}


def authorize_with_camel(camel_auth, authorization_url: str) -> str:
    no_redirect = make_opener(no_redirect=True, jar=camel_auth["jar"])
    url = with_query(rewrite_base(authorization_url, CAMEL_API_BASE), consent="allow")
    headers_in = {"Cookie": camel_auth["cookie"]} if camel_auth.get("cookie") else None
    status, _payload, headers = request_url("GET", url, headers=headers_in, opener=no_redirect)
    expect(status in (302, 303), f"CaMeL authorize returned {status}: {_payload!r}")
    location = headers.get("Location") or headers.get("location")
    expect(bool(location), f"CaMeL authorize missing Location header: {headers!r}")
    return str(location)


def arcreel_login_with_camel(camel_jar) -> str:
    arc_jar = http.cookiejar.CookieJar()
    arc_no_redirect = make_opener(no_redirect=True, jar=arc_jar)
    status, _payload, headers = request_url(
        "GET",
        f"{API_BASE}/api/v1/auth/camel/start?from=/app/projects",
        opener=arc_no_redirect,
    )
    expect(status in (302, 303, 307), f"ArcReel camel start returned {status}: {_payload!r}")
    authorization_url = headers.get("Location") or headers.get("location")
    expect(bool(authorization_url), "ArcReel camel start missing Location header")
    callback_location = authorize_with_camel(camel_jar, str(authorization_url))
    callback_url = rewrite_base(callback_location, API_BASE)
    status, _payload, headers = request_url("GET", callback_url, opener=arc_no_redirect)
    expect(status in (302, 303, 307), f"ArcReel camel callback returned {status}: {_payload!r}")
    final_location = headers.get("Location") or headers.get("location")
    expect(bool(final_location), "ArcReel callback missing final Location header")
    _query, fragment = parse_redirect(str(final_location))
    token = (fragment.get("access_token") or [""])[0]
    expect(bool(token), f"ArcReel callback did not return access token: {final_location}")
    return token


def bootstrap_camel_providers(token: str, camel_jar) -> dict:
    arc_jar = http.cookiejar.CookieJar()
    arc_no_redirect = make_opener(no_redirect=True, jar=arc_jar)
    status, payload, _headers = request_url(
        "POST",
        f"{API_BASE}/api/v1/camel/bootstrap/start-url?mode=create",
        headers=bearer(token),
        opener=arc_no_redirect,
    )
    expect(status == 200, f"POST /camel/bootstrap/start-url returned {status}: {payload!r}")
    authorization_url = require_str(payload.get("authorization_url"), f"authorization_url missing: {payload!r}")
    callback_location = authorize_with_camel(camel_jar, authorization_url)
    callback_url = rewrite_base(callback_location, API_BASE)
    status, _payload, headers = request_url("GET", callback_url, opener=arc_no_redirect)
    expect(status in (302, 303, 307), f"ArcReel bootstrap callback returned {status}: {_payload!r}")
    final_location = headers.get("Location") or headers.get("location")
    expect(bool(final_location), "ArcReel bootstrap callback missing Location header")
    query, _fragment = parse_redirect(str(final_location))
    expect(query.get("camel_bootstrap") == ["completed"], f"bootstrap did not complete: {final_location}")
    result_raw = (query.get("camel_bootstrap_result") or ["{}"])[0]
    return json.loads(result_raw)


def create_project(token: str, name: str, title: str) -> None:
    status, payload, _ = request(
        "POST",
        "/api/v1/projects",
        body={"name": name, "title": title, "content_mode": "narration"},
        headers=bearer(token),
    )
    expect(status == 200, f"POST /projects {name} returned {status}: {payload!r}")


def put_source(token: str, project: str, filename: str, content: str) -> None:
    status, payload, _ = request(
        "PUT",
        f"/api/v1/projects/{project}/source/{filename}",
        raw=content,
        headers={**bearer(token), "Content-Type": "text/plain"},
    )
    expect(status == 200, f"PUT source returned {status}: {payload!r}")


def tenant_token(token: str, tenant_id: str) -> str:
    status, payload, _ = request(
        "POST",
        "/api/v1/auth/tenant-token",
        body={"tenant_id": tenant_id},
        headers=bearer(token),
    )
    expect(status == 200, f"POST /auth/tenant-token returned {status}: {payload!r}")
    return require_str(payload.get("access_token"), f"tenant token missing: {payload!r}")


def login_camel_user(username: str, password: str) -> dict:
    camel_jar = camel_login(username, password)
    token = arcreel_login_with_camel(camel_jar)
    status, payload, _ = request("GET", "/api/v1/auth/verify", headers=bearer(token))
    expect(status == 200, f"GET /auth/verify for {username} returned {status}: {payload!r}")
    user_id = require_str(payload.get("user_id"), f"bad ArcReel user id: {payload!r}")
    expect(user_id.startswith("camel:"), f"bad ArcReel user id: {payload!r}")
    return {"username": username, "password": password, "token": token, "user_id": user_id, "camel": camel_jar}


def upload_private_file_request(
    token: str, filename: str, content: bytes, content_type: str = "text/plain"
) -> tuple[int, JsonObject, dict[str, str]]:
    boundary = f"----arcreel-smoke-{uuid.uuid4().hex}"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            content,
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="purpose"\r\n\r\nacceptance\r\n',
            f"--{boundary}--\r\n".encode(),
        ]
    )
    status, payload, _ = request(
        "POST",
        "/api/v1/files",
        raw=body,
        headers={**bearer(token), "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return status, payload, _


def upload_private_file(token: str, filename: str, content: bytes, content_type: str = "text/plain") -> dict:
    status, payload, _ = upload_private_file_request(token, filename, content, content_type)
    expect(status == 200, f"POST /files returned {status}: {payload!r}")
    require_str(payload.get("file_id"), f"file upload payload mismatch: {payload!r}")
    return payload


def get_signed_file_url(token: str, file_id: str) -> str:
    status, payload, _ = request("GET", f"/api/v1/files/{file_id}/signed-url", headers=bearer(token))
    expect(status == 200, f"GET /files/{file_id}/signed-url returned {status}: {payload!r}")
    return require_str(payload.get("url"), f"signed url missing: {payload!r}")


def get_json(path: str, token: str):
    return request("GET", path, headers=bearer(token))


def verify_user_configuration(user: dict) -> dict:
    token = user["token"]
    status, payload, _ = get_json("/api/v1/custom-providers", token)
    expect(status == 200, f"GET custom providers returned {status}")
    providers = payload.get("providers") or []
    expect(len(providers) == 4, f"expected 4 custom providers, got {payload!r}")
    provider_ids = {int(p["id"]) for p in providers}
    for provider in providers:
        expect(provider.get("base_url") == EXPECTED_PROVIDER_BASE_URL, f"provider base_url mismatch: {provider!r}")
        expect(provider.get("display_name", "").startswith("CaMeL "), f"provider name mismatch: {provider!r}")

    status, payload, _ = get_json("/api/v1/system/config", token)
    expect(status == 200, f"GET system config returned {status}")
    settings = payload.get("settings") or {}
    for key in (
        "default_video_backend",
        "default_image_backend_t2i",
        "default_image_backend_i2i",
        "default_text_backend",
        "default_audio_backend",
    ):
        value = require_str(settings.get(key), f"{key} not custom: {settings!r}")
        expect(value.startswith("custom-"), f"{key} not custom: {settings!r}")
        provider_part = value.split("/", 1)[0]
        expect(int(provider_part.removeprefix("custom-")) in provider_ids, f"{key} points to another provider: {value}")
    return {"provider_ids": provider_ids, "settings": settings}


def run_multi_user_flow(checks: list[str]) -> None:
    ensure_camel_root()
    run_id = os.environ.get("SMOKE_RUN_ID") or uuid.uuid4().hex[:8]
    password = "ArcReel1234"
    users: list[dict] = []
    for index in range(1, 4):
        username = f"arc-smoke-{run_id}-{index}"
        camel_jar = camel_login(username, password)
        token = arcreel_login_with_camel(camel_jar)
        status, payload, _ = request("GET", "/api/v1/auth/verify", headers=bearer(token))
        expect(status == 200, f"GET /auth/verify for {username} returned {status}")
        user_id = require_str(payload.get("user_id"), f"bad ArcReel user id: {payload!r}")
        expect(user_id.startswith("camel:"), f"bad ArcReel user id: {payload!r}")
        result = bootstrap_camel_providers(token, camel_jar)
        expect(result.get("completed") is True, f"bootstrap result mismatch: {result!r}")
        users.append({"username": username, "token": token, "user_id": user_id})
    checks.append("camel oauth login for three users")
    checks.append("camel provider bootstrap for three users")

    for user in users:
        token = user["token"]
        create_project(token, "common", f"{user['username']} Common")
        create_project(token, f"{user['username']}-private", f"{user['username']} Private")
        put_source(token, f"{user['username']}-private", "chapter.txt", f"source for {user['username']}")
    checks.append("three users created projects and files")

    configs = {user["username"]: verify_user_configuration(user) for user in users}
    checks.append("custom providers and default model settings scoped per user")

    for user in users:
        status, payload, _ = get_json("/api/v1/projects", user["token"])
        expect(status == 200, f"GET projects returned {status}")
        titles = {p.get("title") for p in payload.get("projects") or []}
        names = {p.get("name") for p in payload.get("projects") or []}
        expect(names == {"common", f"{user['username']}-private"}, f"project list leaked or missed data: {payload!r}")
        expect(
            titles == {f"{user['username']} Common", f"{user['username']} Private"},
            f"project titles leaked or missed data: {payload!r}",
        )
    checks.append("project lists isolated")

    first, second = users[0], users[1]
    first_private = f"{first['username']}-private"
    status, body, _ = request(
        "GET", f"/api/v1/files/{first_private}/source/chapter.txt", headers=bearer(first["token"])
    )
    expect(
        status == 200 and raw_text(body) == f"source for {first['username']}",
        f"owner file read failed: {status} {body!r}",
    )
    status, payload, _ = request(
        "GET",
        f"/api/v1/files/{first_private}/source/chapter.txt",
        headers=bearer(second["token"]),
    )
    expect(status == 404, f"cross-user file read returned {status}: {payload!r}")
    status, payload, _ = request("GET", f"/api/v1/files/{first_private}/source/chapter.txt")
    expect(status == 401, f"anonymous file read returned {status}: {payload!r}")
    checks.append("direct file URL access scoped")

    first_provider_id = next(iter(configs[first["username"]]["provider_ids"]))
    status, payload, _ = get_json(f"/api/v1/custom-providers/{first_provider_id}", second["token"])
    expect(status == 404, f"cross-user custom provider read returned {status}: {payload!r}")
    checks.append("custom provider ids isolated")

    def list_projects(user: dict):
        return get_json("/api/v1/projects", user["token"])

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(list_projects, users))
    for status, payload, _ in results:
        expect(status == 200, f"concurrent project request returned {status}: {payload!r}")
    checks.append("parallel authenticated requests preserved user scope")


def run_tenant_role_and_minio_flow(checks: list[str]) -> None:
    ensure_camel_root()
    run_id = os.environ.get("SMOKE_RUN_ID") or uuid.uuid4().hex[:8]
    password = "ArcReel1234"
    owner = login_camel_user(f"own-{run_id}", password)
    admin = login_camel_user(f"adm-{run_id}", password)
    member = login_camel_user(f"mem-{run_id}", password)
    viewer = login_camel_user(f"vie-{run_id}", password)
    outsider = login_camel_user(f"out-{run_id}", password)

    status, payload, _ = request(
        "POST",
        "/api/v1/tenants",
        body={"name": f"Smoke Team {run_id}"},
        headers=bearer(owner["token"]),
    )
    expect(status == 200, f"POST /tenants returned {status}: {payload!r}")
    tenant_id = require_str(payload.get("id"), f"tenant id missing: {payload!r}")
    owner_team_token = tenant_token(owner["token"], tenant_id)

    status, payload, _ = request(
        "POST",
        "/api/v1/tenant/members",
        body={"user_id": admin["user_id"], "role": "admin"},
        headers=bearer(owner_team_token),
    )
    expect(status == 200 and payload.get("role") == "admin", f"owner add admin failed: {status} {payload!r}")
    admin_team_token = tenant_token(admin["token"], tenant_id)

    status, payload, _ = request(
        "POST",
        "/api/v1/tenant/members",
        body={"user_id": member["user_id"], "role": "member"},
        headers=bearer(admin_team_token),
    )
    expect(status == 200 and payload.get("role") == "member", f"admin add member failed: {status} {payload!r}")
    member_team_token = tenant_token(member["token"], tenant_id)

    status, payload, _ = request(
        "POST",
        "/api/v1/tenant/members",
        body={"user_id": viewer["user_id"], "role": "view"},
        headers=bearer(member_team_token),
    )
    expect(status == 200 and payload.get("role") == "view", f"member add viewer failed: {status} {payload!r}")
    viewer_team_token = tenant_token(viewer["token"], tenant_id)
    checks.append("tenant owner/admin/member/view positive role grants")

    status, payload, _ = request(
        "POST",
        "/api/v1/tenant/members",
        body={"user_id": outsider["user_id"], "role": "admin"},
        headers=bearer(admin_team_token),
    )
    expect(status == 403, f"non-owner admin assignment returned {status}: {payload!r}")
    status, payload, _ = request(
        "POST",
        "/api/v1/tenant/members",
        body={"user_id": outsider["user_id"], "role": "member"},
        headers=bearer(member_team_token),
    )
    expect(status == 403, f"member assignment by member returned {status}: {payload!r}")
    status, payload, _ = request(
        "POST",
        "/api/v1/auth/tenant-token",
        body={"tenant_id": tenant_id},
        headers=bearer(outsider["token"]),
    )
    expect(status == 403, f"outsider tenant token returned {status}: {payload!r}")
    checks.append("tenant role escalation and outsider access denied")

    status, payload, _ = request(
        "GET",
        f"/api/v1/tenant/users/search?q={urllib.parse.quote(outsider['username'])}",
        headers=bearer(viewer_team_token),
    )
    expect(status == 403, f"viewer user search returned {status}: {payload!r}")
    status, payload, _ = request(
        "GET",
        f"/api/v1/tenant/users/search?q={urllib.parse.quote(outsider['username'])}",
        headers=bearer(member_team_token),
    )
    expect(status == 200 and bool(payload.get("users")), f"member user search failed: {status} {payload!r}")
    checks.append("active user search limited to writable tenant roles")

    project_name = f"team-{run_id}"
    create_project(member_team_token, project_name, f"Team Project {run_id}")
    put_source(member_team_token, project_name, "chapter.txt", f"team source {run_id}")
    status, body, _ = request(
        "GET",
        f"/api/v1/files/{project_name}/source/chapter.txt",
        headers=bearer(viewer_team_token),
    )
    expect(
        status == 200 and raw_text(body) == f"team source {run_id}",
        f"viewer project read failed: {status} {body!r}",
    )
    status, payload, _ = request(
        "PUT",
        f"/api/v1/projects/{project_name}/source/chapter.txt",
        raw="viewer overwrite",
        headers={**bearer(viewer_team_token), "Content-Type": "text/plain"},
    )
    expect(status == 403, f"viewer project write returned {status}: {payload!r}")
    status, payload, _ = request(
        "GET",
        f"/api/v1/files/{project_name}/source/chapter.txt",
        headers=bearer(outsider["token"]),
    )
    expect(status in (403, 404), f"outsider project file read returned {status}: {payload!r}")
    checks.append("tenant project member write, viewer read, outsider denied")

    status, payload, _ = upload_private_file_request(viewer_team_token, f"viewer-{run_id}.txt", b"viewer")
    expect(status == 403, f"viewer private file upload returned {status}: {payload!r}")
    file_payload = upload_private_file(
        member_team_token,
        f"proof-{run_id}.txt",
        f"minio proof {run_id}".encode(),
    )
    file_id = require_str(file_payload.get("file_id"), f"file id missing: {file_payload!r}")
    expect(file_id.startswith("fil_"), f"file id shape mismatch: {file_payload!r}")
    viewer_url = get_signed_file_url(viewer_team_token, file_id)
    status, body, _ = request_url("GET", viewer_url)
    expect(
        status == 200 and raw_text(body) == f"minio proof {run_id}",
        f"signed file read failed: {status} {body!r}",
    )
    status, payload, _ = request("GET", f"/api/v1/files/{file_id}/signed-url", headers=bearer(outsider["token"]))
    expect(status == 403, f"outsider signed url returned {status}: {payload!r}")
    tampered_url = viewer_url[:-1] + ("a" if viewer_url[-1] != "a" else "b")
    status, payload, _ = request_url("GET", tampered_url)
    expect(status == 403, f"tampered signed url returned {status}: {payload!r}")
    checks.append("minio private file signed-url and token corner cases")

    status, payload, _ = request(
        "POST",
        "/api/v1/assets",
        body={"library": "tenant", "type": "character", "name": f"Role {run_id}", "image_file_id": file_id},
        headers=bearer(member_team_token),
    )
    expect(status == 200, f"member asset create with file id returned {status}: {payload!r}")
    asset = require_object(payload.get("asset"), f"asset missing: {payload!r}")
    asset_id = require_str(asset.get("id"), f"asset id missing: {payload!r}")
    status, payload, _ = request(
        "POST",
        "/api/v1/assets",
        body={"library": "tenant", "type": "character", "name": f"View {run_id}", "image_file_id": file_id},
        headers=bearer(viewer_team_token),
    )
    expect(status == 403, f"viewer asset create returned {status}: {payload!r}")
    status, payload, _ = request(
        "POST",
        "/api/v1/assets/import",
        body={"source_binding_id": asset_id, "target_library": "personal"},
        headers=bearer(viewer_team_token),
    )
    expect(status == 403, f"viewer import to personal returned {status}: {payload!r}")
    checks.append("asset library file-id write requires member role")


def main() -> None:
    checks: list[str] = []
    run_id = os.environ.get("SMOKE_RUN_ID") or uuid.uuid4().hex[:8]

    status, payload, _ = request("GET", "/health")
    expect(status == 200, f"GET /health returned {status}")
    expect(payload.get("status") == "ok", f"unexpected health payload: {payload!r}")
    checks.append("health")

    status, payload, _ = request("GET", "/api/v1/auth/status")
    expect(status == 200, f"GET /auth/status returned {status}")
    expect(payload.get("enabled") is True, f"auth enabled mismatch: {payload!r}")
    expect(payload.get("mode") == "camel", f"auth mode mismatch: {payload!r}")
    providers = payload.get("providers") or []
    expect(any(p.get("id") == "camel" for p in providers), f"camel provider missing: {payload!r}")
    checks.append("camel auth status")

    status, payload, _ = request(
        "POST",
        "/api/v1/auth/token",
        form={"username": "admin", "password": "password"},
    )
    expect(status == 403, f"local auth token in camel mode returned {status}")
    checks.append("local login disabled")

    ensure_camel_root()
    primary_camel = camel_login(f"arc-pri-{run_id}", "ArcReel1234")
    primary_token = arcreel_login_with_camel(primary_camel)
    status, payload, _ = request("GET", "/api/v1/auth/verify", headers=bearer(primary_token))
    expect(status == 200, f"GET /auth/verify returned {status}")
    expect(payload.get("valid") is True, f"verify valid mismatch: {payload!r}")
    expect(str(payload.get("user_id", "")).startswith("camel:"), f"verify user_id mismatch: {payload!r}")
    expect(payload.get("provider") == "camel", f"verify provider mismatch: {payload!r}")
    checks.append("camel oauth tenant token verify")

    status, payload, _ = request("GET", "/api/v1/auth/me", headers=bearer(primary_token))
    expect(status == 200, f"GET /auth/me returned {status}: {payload!r}")
    tenant = require_object(payload.get("tenant"), f"tenant missing: {payload!r}")
    expect(tenant.get("role") == "admin", f"personal tenant role mismatch: {payload!r}")
    expect(tenant.get("personal") is True, f"personal tenant flag mismatch: {payload!r}")
    expect(str(tenant.get("name", "")).endswith("的个人空间"), f"personal tenant name mismatch: {payload!r}")
    checks.append("default personal tenant")

    status, payload, _ = request("GET", "/api/v1/camel/bootstrap/status", headers=bearer(primary_token))
    expect(status == 200, f"GET /camel/bootstrap/status returned {status}")
    expect(
        payload.get("needed") is True and payload.get("completed") is False, f"bootstrap status mismatch: {payload!r}"
    )
    expect(bool(str(payload.get("camel_user_id", ""))), f"camel user id mismatch: {payload!r}")
    bootstrap_providers = payload.get("providers") or []
    video_provider = require_object(
        next((p for p in bootstrap_providers if isinstance(p, dict) and p.get("media") == "video"), None),
        f"video provider missing: {payload!r}",
    )
    expect(video_provider.get("endpoint") == "ark-seedance", f"video endpoint mismatch: {video_provider!r}")
    expect(video_provider.get("base_url") == EXPECTED_PROVIDER_BASE_URL, f"video base_url mismatch: {video_provider!r}")
    expect(
        "doubao-seedance-2-0-260128" in (video_provider.get("models") or []), f"video model missing: {video_provider!r}"
    )
    checks.append("camel bootstrap status")

    status, payload, headers = request(
        "POST", "/api/v1/camel/bootstrap/start-url?mode=create", headers=bearer(primary_token)
    )
    expect(status == 200, f"POST /camel/bootstrap/start-url returned {status}")
    auth_url = require_str(payload.get("authorization_url"), f"authorization_url missing: {payload!r}")
    parsed = urllib.parse.urlparse(auth_url)
    query = urllib.parse.parse_qs(parsed.query)
    expect(
        parsed.geturl().startswith("http://localhost:13080/api/oauth/provider/authorize"), f"bad auth url: {auth_url}"
    )
    expect(query.get("client_id") == ["arc-test-client"], f"client_id missing: {auth_url}")
    expect("arcreel:token-provision" in query.get("scope", [""])[0], f"bootstrap scope missing: {auth_url}")
    expect("set-cookie" in {k.lower() for k in headers}, "state cookie missing")
    checks.append("bootstrap start-url")

    status, payload, _ = request("GET", "/api/v1/custom-providers/endpoints", headers=bearer(primary_token))
    expect(status == 200, f"GET /custom-providers/endpoints returned {status}")
    endpoints = payload.get("endpoints") or []
    seedance = require_object(
        next((e for e in endpoints if isinstance(e, dict) and e.get("key") == "ark-seedance"), None),
        "ark-seedance endpoint missing",
    )
    expect(
        seedance.get("request_path_template") == "/api/v3/contents/generations/tasks",
        f"ark-seedance path mismatch: {seedance!r}",
    )
    checks.append("seedance endpoint catalog")

    status, payload, _ = request("GET", "/api/v1/providers", headers=bearer(primary_token))
    expect(status == 200, f"GET /providers returned {status}")
    expect(isinstance(payload.get("providers"), list), f"providers payload mismatch: {payload!r}")
    checks.append("providers list")

    run_multi_user_flow(checks)
    run_tenant_role_and_minio_flow(checks)

    print(json.dumps({"ok": True, "checks": checks}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
