from __future__ import annotations

import json
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from pydantic import AnyHttpUrl, SecretStr


class BronzeStore(Protocol):
    def put_bytes(self, object_key: str, payload: bytes, content_type: str) -> None:
        raise NotImplementedError


class NullBronzeStore:
    def __init__(self) -> None:
        self.uploads: list[str] = []

    def put_bytes(self, object_key: str, payload: bytes, content_type: str) -> None:
        del payload, content_type
        self.uploads.append(object_key)


class MinioBronzeStore:
    def __init__(
        self,
        endpoint_url: AnyHttpUrl | str,
        access_key: SecretStr | str,
        secret_key: SecretStr | str,
        bucket: str,
    ) -> None:
        from minio import Minio

        parsed = urlparse(str(endpoint_url))
        access = access_key.get_secret_value() if isinstance(access_key, SecretStr) else access_key
        secret = secret_key.get_secret_value() if isinstance(secret_key, SecretStr) else secret_key
        self._bucket = bucket
        self._client = Minio(
            parsed.netloc,
            access_key=access,
            secret_key=secret,
            secure=parsed.scheme == "https",
        )
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)

    def put_bytes(self, object_key: str, payload: bytes, content_type: str) -> None:
        self._client.put_object(
            self._bucket,
            object_key,
            BytesIO(payload),
            length=len(payload),
            content_type=content_type,
        )


def bronze_prefix(department_id: str, module_code: str, release_id: str) -> str:
    return f"{department_id}/{module_code}/{release_id}"


def upload_bronze_snapshot(
    store: BronzeStore,
    *,
    department_id: str,
    module_code: str,
    release_id: str,
    files: Mapping[str, Path],
    checksums: Mapping[str, object],
    report_json: bytes,
) -> list[str]:
    prefix = bronze_prefix(department_id, module_code, release_id)
    keys: list[str] = []
    for name, path in files.items():
        key = f"{prefix}/{name}"
        store.put_bytes(
            key,
            path.read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        keys.append(key)
    checksum_key = f"{prefix}/checksums.json"
    store.put_bytes(
        checksum_key,
        json.dumps(checksums, ensure_ascii=False, indent=2).encode("utf-8"),
        "application/json",
    )
    keys.append(checksum_key)
    report_key = f"{prefix}/validation.json"
    store.put_bytes(report_key, report_json, "application/json")
    keys.append(report_key)
    return keys
