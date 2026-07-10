from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

API_BASE = os.environ["ARCREEL_API_BASE_URL"].rstrip("/")
CAMEL_API_BASE = os.environ["CAMEL_API_BASE_URL"].rstrip("/")
CAMEL_ROOT_USERNAME = os.environ.get("CAMEL_ROOT_USERNAME", "root")
CAMEL_ROOT_PASSWORD = os.environ.get("CAMEL_ROOT_PASSWORD", "test-root-password")
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


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def make_opener(*, no_redirect: bool = False, jar: http.cookiejar.CookieJar | None = None):
    cookie_jar = jar or http.cookiejar.CookieJar()
    handlers: list[urllib.request.BaseHandler] = [urllib.request.HTTPCookieProcessor(cookie_jar)]
    if no_redirect:
        handlers.append(NoRedirect())
    return urllib.request.build_opener(*handlers)


def request_url(
    method: str,
    url: str,
    *,
    body: dict | None = None,
    headers: dict | None = None,
    raw: bytes | str | None = None,
    opener=None,
) -> tuple[int, JsonObject, dict[str, str]]:
    data = None
    req_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    if raw is not None:
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        open_fn = opener.open if opener is not None else urllib.request.urlopen
        with open_fn(req, timeout=20) as response:
            content = response.read()
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return response.status, json.loads(content.decode("utf-8")), dict(response.headers)
            return response.status, {"raw": content.decode("utf-8", errors="replace")}, dict(response.headers)
    except urllib.error.HTTPError as exc:
        content = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {"raw": content}
        return exc.code, parsed, dict(exc.headers)


def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict | None = None,
    raw: bytes | str | None = None,
    headers: dict | None = None,
) -> tuple[int, JsonObject, dict[str, str]]:
    merged = dict(headers or {})
    if token is not None:
        merged["Authorization"] = f"Bearer {token}"
    return request_url(method, API_BASE + path, body=body, raw=raw, headers=merged)


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


def cookie_header(headers: dict) -> str:
    raw = headers.get("Set-Cookie") or headers.get("set-cookie") or ""
    return raw.split(";", 1)[0] if raw else ""


def expect_success_payload(payload: JsonObject, label: str) -> None:
    expect(payload.get("success") is True, f"{label}: success was not true: {payload!r}")


def raw_text(payload: JsonObject) -> str:
    value = payload.get("raw")
    return value if isinstance(value, str) else ""


def require_str(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value:
        raise SmokeFailure(message)
    return value


def ensure_camel_root() -> None:
    status, payload, _ = request_url("GET", f"{CAMEL_API_BASE}/api/setup")
    expect(status == 200, f"GET /api/setup returned {status}: {payload!r}")
    expect_success_payload(payload, "GET /api/setup")
    if (payload.get("data") or {}).get("status") is True:
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
    expect(status == 200, f"POST /api/setup returned {status}: {payload!r}")
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
        expect("exist" in message.lower() or "已存在" in message, f"register returned {status}: {payload!r}")
    status, payload, headers = request_url(
        "POST",
        f"{CAMEL_API_BASE}/api/user/login",
        body={"username": username, "password": password},
        opener=opener,
    )
    expect(status == 200, f"login returned {status}: {payload!r}")
    expect_success_payload(payload, "POST /api/user/login")
    return {"jar": jar, "cookie": cookie_header(headers)}


def authorize_with_camel(camel_auth, authorization_url: str) -> str:
    no_redirect = make_opener(no_redirect=True, jar=camel_auth["jar"])
    url = with_query(rewrite_base(authorization_url, CAMEL_API_BASE), consent="allow")
    headers = {"Cookie": camel_auth["cookie"]} if camel_auth.get("cookie") else None
    status, payload, response_headers = request_url("GET", url, headers=headers, opener=no_redirect)
    expect(status in (302, 303), f"CaMeL authorize returned {status}: {payload!r}")
    location = response_headers.get("Location") or response_headers.get("location")
    expect(bool(location), f"CaMeL authorize missing Location header: {response_headers!r}")
    return str(location)


def arcreel_login_with_camel(camel_auth) -> str:
    arc_no_redirect = make_opener(no_redirect=True)
    status, payload, headers = request_url(
        "GET",
        f"{API_BASE}/api/v1/auth/camel/start?from=/app/projects",
        opener=arc_no_redirect,
    )
    expect(status in (302, 303, 307), f"ArcReel camel start returned {status}: {payload!r}")
    authorization_url = headers.get("Location") or headers.get("location")
    expect(bool(authorization_url), "ArcReel camel start missing Location header")
    callback_location = authorize_with_camel(camel_auth, str(authorization_url))
    status, payload, headers = request_url("GET", rewrite_base(callback_location, API_BASE), opener=arc_no_redirect)
    expect(status in (302, 303, 307), f"ArcReel callback returned {status}: {payload!r}")
    final_location = headers.get("Location") or headers.get("location")
    expect(bool(final_location), "ArcReel callback missing final Location header")
    _query, fragment = parse_redirect(str(final_location))
    token = (fragment.get("access_token") or [""])[0]
    expect(bool(token), f"ArcReel callback did not return access token: {final_location}")
    return token


def login_user(prefix: str, run_id: str) -> dict:
    camel = camel_login(f"{prefix}-{run_id}", "ArcReel1234")
    token = arcreel_login_with_camel(camel)
    status, payload, _ = request("GET", "/api/v1/auth/verify", token=token)
    expect(status == 200, f"verify returned {status}: {payload!r}")
    user_id = require_str(payload.get("user_id"), f"bad user id: {payload!r}")
    expect(user_id.startswith("camel:"), f"bad user id: {payload!r}")
    return {"token": token, "user_id": user_id}


def tenant_token(token: str, tenant_id: str) -> str:
    status, payload, _ = request("POST", "/api/v1/auth/tenant-token", token=token, body={"tenant_id": tenant_id})
    expect(status == 200, f"tenant-token returned {status}: {payload!r}")
    return require_str(payload.get("access_token"), f"tenant token missing: {payload!r}")


def add_member(actor_token: str, user_id: str, role: str, expected_status: int = 200) -> dict:
    status, payload, _ = request(
        "POST",
        "/api/v1/tenant/members",
        token=actor_token,
        body={"user_id": user_id, "role": role},
    )
    expect(status == expected_status, f"add {role} returned {status}: {payload!r}")
    return payload


def upload_private_file(token: str, filename: str, content: bytes, expected_status: int = 200) -> dict:
    boundary = f"----arcreel-smoke-{uuid.uuid4().hex}"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: text/plain\r\n\r\n",
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
        token=token,
        raw=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    expect(status == expected_status, f"upload file returned {status}: {payload!r}")
    return payload


def create_project(token: str, name: str, title: str, expected_status: int = 200) -> None:
    status, payload, _ = request(
        "POST",
        "/api/v1/projects",
        token=token,
        body={"name": name, "title": title, "content_mode": "narration"},
    )
    expect(status == expected_status, f"create project returned {status}: {payload!r}")


def put_source(token: str, project: str, expected_status: int = 200) -> None:
    status, payload, _ = request(
        "PUT",
        f"/api/v1/projects/{project}/source/chapter.txt",
        token=token,
        raw="tenant source",
        headers={"Content-Type": "text/plain"},
    )
    expect(status == expected_status, f"put source returned {status}: {payload!r}")


def signed_content(token: str, file_id: str, expected_status: int = 200) -> str:
    status, payload, _ = request("GET", f"/api/v1/files/{file_id}/signed-url", token=token)
    expect(status == expected_status, f"signed-url returned {status}: {payload!r}")
    if expected_status != 200:
        return ""
    url = require_str(payload.get("url"), f"signed-url missing: {payload!r}")
    status, content, _ = request_url("GET", url)
    expect(status == 200, f"signed content returned {status}: {content!r}")
    return raw_text(content)


def main() -> None:
    ensure_camel_root()
    run_id = os.environ.get("SMOKE_RUN_ID") or uuid.uuid4().hex[:8]
    owner = login_user("own", run_id)
    admin = login_user("adm", run_id)
    member = login_user("mem", run_id)
    viewer = login_user("vie", run_id)
    outsider = login_user("out", run_id)

    status, payload, _ = request("POST", "/api/v1/tenants", token=owner["token"], body={"name": f"Team {run_id}"})
    expect(status == 200, f"create tenant returned {status}: {payload!r}")
    tenant_id = require_str(payload.get("id"), f"tenant id missing: {payload!r}")

    owner_team = tenant_token(owner["token"], tenant_id)
    add_member(owner_team, admin["user_id"], "admin")
    admin_team = tenant_token(admin["token"], tenant_id)
    add_member(admin_team, member["user_id"], "member")
    member_team = tenant_token(member["token"], tenant_id)
    add_member(member_team, viewer["user_id"], "view")
    viewer_team = tenant_token(viewer["token"], tenant_id)

    add_member(admin_team, outsider["user_id"], "admin", expected_status=403)
    add_member(member_team, outsider["user_id"], "member", expected_status=403)
    status, payload, _ = request(
        "POST", "/api/v1/auth/tenant-token", token=outsider["token"], body={"tenant_id": tenant_id}
    )
    expect(status == 403, f"outsider tenant-token returned {status}: {payload!r}")

    status, payload, _ = request("GET", "/api/v1/tenant/members", token=viewer_team)
    expect(status == 200, f"viewer member list returned {status}: {payload!r}")
    roles = {item.get("user_id"): item.get("role") for item in payload.get("members", [])}
    expect(roles.get(owner["user_id"]) == "admin", f"owner role missing: {payload!r}")
    expect(roles.get(admin["user_id"]) == "admin", f"admin role missing: {payload!r}")
    expect(roles.get(member["user_id"]) == "member", f"member role missing: {payload!r}")
    expect(roles.get(viewer["user_id"]) == "view", f"viewer role missing: {payload!r}")

    project_name = f"tenant-{run_id}"
    create_project(member_team, project_name, f"Tenant {run_id}")
    create_project(viewer_team, f"viewer-{run_id}", "Viewer Forbidden", expected_status=403)
    put_source(member_team, project_name)
    put_source(viewer_team, project_name, expected_status=403)
    status, body, _ = request("GET", f"/api/v1/files/{project_name}/source/chapter.txt", token=viewer_team)
    expect(status == 200 and raw_text(body) == "tenant source", f"viewer source read failed: {status} {body!r}")
    status, payload, _ = request("GET", f"/api/v1/files/{project_name}/source/chapter.txt", token=outsider["token"])
    expect(status == 403 or status == 404, f"outsider source read returned {status}: {payload!r}")

    uploaded = upload_private_file(member_team, "proof.txt", b"tenant minio proof")
    file_id = require_str(uploaded.get("file_id"), f"file id missing: {uploaded!r}")
    expect(file_id.startswith("fil_"), f"file id missing: {uploaded!r}")
    expect(signed_content(member_team, file_id) == "tenant minio proof", "member signed content mismatch")
    expect(signed_content(viewer_team, file_id) == "tenant minio proof", "viewer signed content mismatch")
    signed_content(outsider["token"], file_id, expected_status=403)
    upload_private_file(viewer_team, "viewer.txt", b"viewer forbidden", expected_status=403)

    status, payload, _ = request(
        "POST",
        "/api/v1/assets",
        token=member_team,
        body={"library": "tenant", "type": "character", "name": f"Role {run_id}", "image_file_id": file_id},
    )
    expect(status == 200, f"member tenant asset create returned {status}: {payload!r}")
    status, payload, _ = request(
        "POST",
        "/api/v1/assets",
        token=viewer_team,
        body={"library": "tenant", "type": "character", "name": f"Viewer {run_id}", "image_file_id": file_id},
    )
    expect(status == 403, f"viewer tenant asset create returned {status}: {payload!r}")

    checks = [
        "tenant owner/admin/member/view role boundaries",
        "tenant member project write and viewer read-only",
        "minio private file signed-url and cross-tenant denial",
        "tenant asset create uses file_id with member-only write",
    ]
    print(json.dumps({"ok": True, "checks": checks}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
