from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

import httpx


@dataclass(frozen=True)
class MinIOSettings:
    endpoint: str
    public_endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    region: str

    @classmethod
    def from_env(cls) -> MinIOSettings:
        endpoint = os.environ.get("ARCREEL_MINIO_ENDPOINT", "http://127.0.0.1:19000").rstrip("/")
        return cls(
            endpoint=endpoint,
            public_endpoint=os.environ.get("ARCREEL_MINIO_PUBLIC_ENDPOINT", endpoint).rstrip("/"),
            access_key=os.environ.get("ARCREEL_MINIO_ACCESS_KEY", "arcreelminio"),
            secret_key=os.environ.get("ARCREEL_MINIO_SECRET_KEY", "arcreel_minio_dev_password"),
            bucket=os.environ.get("ARCREEL_MINIO_BUCKET", "arcreel-files"),
            region=os.environ.get("ARCREEL_MINIO_REGION", "us-east-1"),
        )


@dataclass(frozen=True)
class ObjectStat:
    size_bytes: int
    content_type: str | None
    etag: str | None


class MinIOStorageService:
    def __init__(self, settings: MinIOSettings | None = None, *, client: httpx.AsyncClient | None = None):
        self.settings = settings or MinIOSettings.from_env()
        self._client = client or httpx.AsyncClient(timeout=60)

    async def put_object(self, object_key: str, content: bytes, *, content_type: str | None = None) -> None:
        headers = {"content-type": content_type} if content_type else {}
        response = await self._client.request(
            "PUT",
            self._object_url(object_key),
            content=content,
            headers=self._signed_headers("PUT", object_key, content, headers),
        )
        response.raise_for_status()

    async def get_object(self, object_key: str) -> bytes:
        response = await self._client.request(
            "GET",
            self._object_url(object_key),
            headers=self._signed_headers("GET", object_key, b"", {}),
        )
        response.raise_for_status()
        return response.content

    async def stat_object(self, object_key: str) -> ObjectStat:
        response = await self._client.request(
            "HEAD",
            self._object_url(object_key),
            headers=self._signed_headers("HEAD", object_key, b"", {}),
        )
        response.raise_for_status()
        size = int(response.headers.get("content-length") or 0)
        return ObjectStat(
            size_bytes=size,
            content_type=response.headers.get("content-type"),
            etag=response.headers.get("etag"),
        )

    async def delete_object(self, object_key: str) -> None:
        response = await self._client.request(
            "DELETE",
            self._object_url(object_key),
            headers=self._signed_headers("DELETE", object_key, b"", {}),
        )
        response.raise_for_status()

    async def bucket_is_private(self) -> bool:
        response = await self._client.get(f"{self.settings.endpoint}/{self.settings.bucket}")
        return response.status_code in {401, 403}

    def signed_get_url(self, object_key: str, *, expires_in: int = 300) -> str:
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        credential_scope = self._credential_scope(date_stamp)
        split = urlsplit(self._object_url(object_key, public=True))
        query = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self.settings.access_key}/{credential_scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expires_in),
            "X-Amz-SignedHeaders": "host",
        }
        canonical_query = urlencode(sorted(query.items()), quote_via=quote, safe="")
        canonical_request = "\n".join(
            [
                "GET",
                split.path,
                canonical_query,
                f"host:{split.netloc}\n",
                "host",
                "UNSIGNED-PAYLOAD",
            ]
        )
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        query["X-Amz-Signature"] = hmac.new(
            self._signing_key(date_stamp),
            string_to_sign.encode(),
            hashlib.sha256,
        ).hexdigest()
        return urlunsplit((split.scheme, split.netloc, split.path, urlencode(sorted(query.items())), ""))

    def _object_url(self, object_key: str, *, public: bool = False) -> str:
        base = self.settings.public_endpoint if public else self.settings.endpoint
        return f"{base}/{self.settings.bucket}/{quote(object_key, safe='/')}"

    def _signed_headers(self, method: str, object_key: str, content: bytes, headers: dict[str, str]) -> dict[str, str]:
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        split = urlsplit(self._object_url(object_key))
        payload_hash = hashlib.sha256(content).hexdigest()
        signed = {
            "host": split.netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            **headers,
        }
        signed_header_names = ";".join(sorted(k.lower() for k in signed))
        canonical_headers = "".join(f"{key.lower()}:{signed[key]}\n" for key in sorted(signed, key=str.lower))
        canonical_request = "\n".join(
            [
                method,
                split.path,
                "",
                canonical_headers,
                signed_header_names,
                payload_hash,
            ]
        )
        credential_scope = self._credential_scope(date_stamp)
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        signature = hmac.new(self._signing_key(date_stamp), string_to_sign.encode(), hashlib.sha256).hexdigest()
        signed["Authorization"] = (
            "AWS4-HMAC-SHA256 "
            f"Credential={self.settings.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_header_names}, "
            f"Signature={signature}"
        )
        return signed

    def _credential_scope(self, date_stamp: str) -> str:
        return f"{date_stamp}/{self.settings.region}/s3/aws4_request"

    def _signing_key(self, date_stamp: str) -> bytes:
        key = hmac.new(f"AWS4{self.settings.secret_key}".encode(), date_stamp.encode(), hashlib.sha256).digest()
        key = hmac.new(key, self.settings.region.encode(), hashlib.sha256).digest()
        key = hmac.new(key, b"s3", hashlib.sha256).digest()
        return hmac.new(key, b"aws4_request", hashlib.sha256).digest()


def get_storage_service() -> MinIOStorageService:
    return MinIOStorageService()
