from __future__ import annotations

import base64
import http.cookiejar
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor


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
):
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
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return response.status, json.loads(raw.decode("utf-8")), dict(response.headers)
            return response.status, raw.decode("utf-8", errors="replace"), dict(response.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed, dict(exc.headers)


def request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    headers: dict | None = None,
    form: dict | None = None,
    raw: bytes | str | None = None,
):
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
    handlers = [urllib.request.HTTPCookieProcessor(cookie_jar)]
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


def expect_success_payload(payload: dict, label: str) -> None:
    expect(isinstance(payload, dict), f"{label}: payload is not an object")
    expect(payload.get("success") is True, f"{label}: success was not true: {payload!r}")


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
    if status != 200 or not (isinstance(payload, dict) and payload.get("success") is True):
        message = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else str(payload)
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
    authorization_url = payload.get("authorization_url") if isinstance(payload, dict) else None
    expect(isinstance(authorization_url, str), f"authorization_url missing: {payload!r}")
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
        value = settings.get(key)
        expect(isinstance(value, str) and value.startswith("custom-"), f"{key} not custom: {settings!r}")
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
        user_id = payload.get("user_id")
        expect(isinstance(user_id, str) and user_id.startswith("camel:"), f"bad ArcReel user id: {payload!r}")
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
    status, body, _ = request("GET", f"/api/v1/files/{first_private}/source/chapter.txt", headers=bearer(first["token"]))
    expect(status == 200 and body == f"source for {first['username']}", f"owner file read failed: {status} {body!r}")
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


def main() -> None:
    checks: list[str] = []

    status, payload, _ = request("GET", "/health")
    expect(status == 200, f"GET /health returned {status}")
    expect(isinstance(payload, dict) and payload.get("status") == "ok", f"unexpected health payload: {payload!r}")
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

    status, payload, _ = request("GET", "/api/v1/auth/verify", headers=bearer())
    expect(status == 200, f"GET /auth/verify returned {status}")
    expect(payload.get("valid") is True, f"verify valid mismatch: {payload!r}")
    expect(payload.get("user_id") == "camel:test-user", f"verify user_id mismatch: {payload!r}")
    expect(payload.get("provider") == "camel", f"verify provider mismatch: {payload!r}")
    checks.append("camel jwt verify")

    status, payload, _ = request("GET", "/api/v1/camel/bootstrap/status", headers=bearer())
    expect(status == 200, f"GET /camel/bootstrap/status returned {status}")
    expect(payload.get("needed") is True and payload.get("completed") is False, f"bootstrap status mismatch: {payload!r}")
    expect(payload.get("camel_user_id") == "test-user", f"camel user id mismatch: {payload!r}")
    bootstrap_providers = payload.get("providers") or []
    video_provider = next((p for p in bootstrap_providers if p.get("media") == "video"), None)
    expect(video_provider is not None, f"video provider missing: {payload!r}")
    expect(video_provider.get("endpoint") == "ark-seedance", f"video endpoint mismatch: {video_provider!r}")
    expect(video_provider.get("base_url") == EXPECTED_PROVIDER_BASE_URL, f"video base_url mismatch: {video_provider!r}")
    expect("doubao-seedance-2-0-260128" in (video_provider.get("models") or []), f"video model missing: {video_provider!r}")
    checks.append("camel bootstrap status")

    status, payload, headers = request("POST", "/api/v1/camel/bootstrap/start-url?mode=create", headers=bearer())
    expect(status == 200, f"POST /camel/bootstrap/start-url returned {status}")
    auth_url = payload.get("authorization_url")
    expect(isinstance(auth_url, str), f"authorization_url missing: {payload!r}")
    parsed = urllib.parse.urlparse(auth_url)
    query = urllib.parse.parse_qs(parsed.query)
    expect(parsed.geturl().startswith("http://localhost:13080/api/oauth/provider/authorize"), f"bad auth url: {auth_url}")
    expect(query.get("client_id") == ["arc-test-client"], f"client_id missing: {auth_url}")
    expect("arcreel:token-provision" in query.get("scope", [""])[0], f"bootstrap scope missing: {auth_url}")
    expect("set-cookie" in {k.lower() for k in headers}, "state cookie missing")
    checks.append("bootstrap start-url")

    status, payload, _ = request("GET", "/api/v1/custom-providers/endpoints", headers=bearer())
    expect(status == 200, f"GET /custom-providers/endpoints returned {status}")
    endpoints = payload.get("endpoints") or []
    seedance = next((e for e in endpoints if e.get("key") == "ark-seedance"), None)
    expect(seedance is not None, "ark-seedance endpoint missing")
    expect(
        seedance.get("request_path_template") == "/api/v3/contents/generations/tasks",
        f"ark-seedance path mismatch: {seedance!r}",
    )
    checks.append("seedance endpoint catalog")

    status, payload, _ = request("GET", "/api/v1/providers", headers=bearer())
    expect(status == 200, f"GET /providers returned {status}")
    expect(isinstance(payload.get("providers"), list), f"providers payload mismatch: {payload!r}")
    checks.append("providers list")

    run_multi_user_flow(checks)

    print(json.dumps({"ok": True, "checks": checks}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
