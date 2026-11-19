from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def insert_many(db, collection: str, docs: list[dict[str, Any]]) -> None:
    if docs:
        db[collection].insert_many(docs)


def find_docs(db, collection: str, filt: dict[str, Any]) -> list[dict[str, Any]]:
    cur = db[collection].find(filt)
    return list(cur)


def delete_module_release(db, collection: str, *, module_code: str, release_id: str) -> None:
    db[collection].delete_many({"module_code": module_code, "release_id": release_id})


def get_active_release(db, module_code: str) -> dict[str, Any] | None:
    return db["releases"].find_one({"module_code": module_code, "active": True})


def deactivate_module_releases(db, module_code: str) -> None:
    for doc in find_docs(db, "releases", {"module_code": module_code, "active": True}):
        db["releases"].update_one(
            {"module_code": module_code, "release_id": doc.get("release_id")},
            {"$set": {"active": False}},
        )


def save_release_meta(db, doc: dict[str, Any]) -> None:
    db["releases"].insert_one(doc)


def activate_release(db, *, module_code: str, release_id: str) -> None:
    deactivate_module_releases(db, module_code)
    db["releases"].update_one(
        {"module_code": module_code, "release_id": release_id},
        {"$set": {"active": True, "activated_at": datetime.now(timezone.utc)}},
    )
