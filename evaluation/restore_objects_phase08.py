"""Back up and restore Qdrant and MinIO into uniquely named disposable targets."""

import hashlib
import io
import json
import uuid
from pathlib import Path

import httpx
from minio import Minio
from qdrant_client import QdrantClient

from app.core.config import Settings


def qdrant_check(settings):
    base = "http://127.0.0.1:6333"
    client = QdrantClient(url=base, timeout=120)
    source = settings.qdrant_collection
    target = "phase08_restore_" + uuid.uuid4().hex
    if client.collection_exists(target):
        raise RuntimeError("generated target already exists")
    snap = client.create_snapshot(source, wait=True)
    if snap is None:
        raise RuntimeError("snapshot was not created")
    created = False
    try:
        response = httpx.get(f"{base}/collections/{source}/snapshots/{snap.name}", timeout=120)
        response.raise_for_status()
        payload = response.content
        if not payload:
            raise RuntimeError("empty snapshot")
        client.http.snapshots_api.recover_from_uploaded_snapshot(
            collection_name=target, wait=True, snapshot=io.BytesIO(payload)
        )
        created = True

        def records(collection):
            output = []
            offset = None
            while True:
                batch, offset = client.scroll(
                    collection, offset=offset, limit=64, with_payload=True, with_vectors=True
                )
                output.extend(item.model_dump(mode="json") for item in batch)
                if offset is None:
                    return sorted(output, key=lambda x: str(x["id"]))

        original, restored = records(source), records(target)
        if not original or original != restored:
            raise RuntimeError("restored Qdrant point data differs")
        return {"status": "passed", "points": len(restored), "snapshot_bytes": len(payload)}
    finally:
        if created or client.collection_exists(target):
            client.delete_collection(target)
        client.delete_snapshot(source, snap.name, wait=True)
        client.close()


def minio_check(settings):
    client = Minio(
        "127.0.0.1:9000",
        access_key=settings.minio_access_key.get_secret_value(),
        secret_key=settings.minio_secret_key.get_secret_value(),
        secure=False,
    )
    target = "phase08-restore-" + uuid.uuid4().hex[:16]
    if client.bucket_exists(target):
        raise RuntimeError("generated bucket already exists")
    archive = []
    for bucket in (settings.minio_bucket_bronze, settings.minio_bucket_attachments):
        if not client.bucket_exists(bucket):
            continue
        for obj in client.list_objects(bucket, recursive=True):
            response = client.get_object(bucket, obj.object_name)
            try:
                data = response.read()
            finally:
                response.close()
                response.release_conn()
            archive.append((bucket + "/" + obj.object_name, data))
    if not archive:
        raise RuntimeError("no source objects to verify")
    client.make_bucket(target)
    try:
        for name, data in archive:
            client.put_object(target, name, io.BytesIO(data), len(data))
        for name, data in archive:
            response = client.get_object(target, name)
            try:
                restored = response.read()
            finally:
                response.close()
                response.release_conn()
            if hashlib.sha256(data).digest() != hashlib.sha256(restored).digest():
                raise RuntimeError("restored object differs")
        return {
            "status": "passed",
            "objects": len(archive),
            "bytes": sum(len(x[1]) for x in archive),
        }
    finally:
        for obj in client.list_objects(target, recursive=True):
            client.remove_object(target, obj.object_name)
        client.remove_bucket(target)


def main():
    settings = Settings()
    result = {"qdrant": qdrant_check(settings), "minio": minio_check(settings)}
    Path("reports/phases/phase-08-object-restore.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
