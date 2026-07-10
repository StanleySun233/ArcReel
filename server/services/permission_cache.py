from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass
from typing import Protocol
from urllib.parse import urlsplit


@dataclass(frozen=True)
class CachedPermission:
    user_id: str
    tenant_id: str
    role: str
    is_owner: bool


class PermissionCache(Protocol):
    async def get(self, user_id: str, tenant_id: str) -> CachedPermission | None: ...

    async def set(self, permission: CachedPermission) -> None: ...

    async def delete(self, user_id: str, tenant_id: str) -> None: ...


class RedisPermissionCache:
    def __init__(self, url: str, *, ttl_seconds: int = 60) -> None:
        self._url = url
        self._ttl_seconds = ttl_seconds

    async def get(self, user_id: str, tenant_id: str) -> CachedPermission | None:
        raw = await self._execute("GET", _key(user_id, tenant_id))
        if raw is None:
            return None
        if not isinstance(raw, bytes):
            return None
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(body, dict):
            return None
        role = body.get("role")
        is_owner = body.get("is_owner")
        if role not in {"admin", "member", "view"} or not isinstance(is_owner, bool):
            return None
        return CachedPermission(user_id=user_id, tenant_id=tenant_id, role=role, is_owner=is_owner)

    async def set(self, permission: CachedPermission) -> None:
        await self._execute(
            "SETEX",
            _key(permission.user_id, permission.tenant_id),
            str(self._ttl_seconds),
            json.dumps(asdict(permission), separators=(",", ":")),
        )

    async def delete(self, user_id: str, tenant_id: str) -> None:
        await self._execute("DEL", _key(user_id, tenant_id))

    async def _execute(self, *parts: str) -> object:
        parsed = urlsplit(self._url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 6379
        db = parsed.path.lstrip("/") or "0"
        reader, writer = await asyncio.open_connection(host, port)
        try:
            if parsed.password:
                if parsed.username:
                    await _write_command(reader, writer, "AUTH", parsed.username, parsed.password)
                else:
                    await _write_command(reader, writer, "AUTH", parsed.password)
            if db != "0":
                await _write_command(reader, writer, "SELECT", db)
            return await _write_command(reader, writer, *parts)
        finally:
            writer.close()
            await writer.wait_closed()


def get_permission_cache() -> PermissionCache | None:
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return None
    return RedisPermissionCache(url)


def _key(user_id: str, tenant_id: str) -> str:
    return f"tenant-permission:{user_id}:{tenant_id}"


async def _write_command(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, *parts: str) -> object:
    encoded_parts = [part.encode("utf-8") for part in parts]
    writer.write(
        b"*" + str(len(encoded_parts)).encode("ascii") + b"\r\n" + b"".join(_bulk(part) for part in encoded_parts)
    )
    await writer.drain()
    return await _read_reply(reader)


def _bulk(value: bytes) -> bytes:
    return b"$" + str(len(value)).encode("ascii") + b"\r\n" + value + b"\r\n"


async def _read_reply(reader: asyncio.StreamReader) -> object:
    prefix = await reader.readexactly(1)
    if prefix == b"+":
        return (await reader.readline()).rstrip(b"\r\n").decode("utf-8")
    if prefix == b":":
        return int((await reader.readline()).rstrip(b"\r\n"))
    if prefix == b"$":
        length = int((await reader.readline()).rstrip(b"\r\n"))
        if length == -1:
            return None
        payload = await reader.readexactly(length)
        await reader.readexactly(2)
        return payload
    if prefix == b"-":
        message = (await reader.readline()).rstrip(b"\r\n").decode("utf-8")
        raise RuntimeError(message)
    raise RuntimeError("Invalid Redis reply")
