from __future__ import annotations

import httpx
import pytest

from lib.storage import MinIOSettings, MinIOStorageService


@pytest.mark.asyncio
async def test_minio_storage_put_get_stat_delete_and_signs_private_object_url() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={"content-length": "5", "content-type": "image/png", "etag": '"abc"'},
                request=request,
            )
        if request.method == "GET":
            return httpx.Response(200, content=b"hello", request=request)
        return httpx.Response(200, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = MinIOStorageService(
        MinIOSettings(
            endpoint="http://minio:9000",
            public_endpoint="https://files.example.test",
            access_key="access",
            secret_key="secret",
            bucket="arcreel-files",
            region="us-east-1",
        ),
        client=client,
    )

    await service.put_object("abc.png", b"hello", content_type="image/png")
    body = await service.get_object("abc.png")
    stat = await service.stat_object("abc.png")
    await service.delete_object("abc.png")
    url = service.signed_get_url("abc.png", expires_in=300)

    assert body == b"hello"
    assert stat.size_bytes == 5
    assert stat.content_type == "image/png"
    assert [request.method for request in requests] == ["PUT", "GET", "HEAD", "DELETE"]
    assert all(request.url.path == "/arcreel-files/abc.png" for request in requests)
    assert all("Authorization" in request.headers for request in requests)
    assert url.startswith("https://files.example.test/arcreel-files/abc.png?")
    assert "X-Amz-Signature=" in url
    assert "X-Amz-Expires=300" in url


@pytest.mark.asyncio
async def test_minio_storage_reports_bucket_private_when_anonymous_access_is_denied() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request)

    service = MinIOStorageService(
        MinIOSettings(
            endpoint="http://minio:9000",
            public_endpoint="https://files.example.test",
            access_key="access",
            secret_key="secret",
            bucket="arcreel-files",
            region="us-east-1",
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    assert await service.bucket_is_private()
