from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.factory import create_app
from fastapi.testclient import TestClient

_API_DIR = Path(__file__).resolve().parents[1]


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []

    def create_index(self, *args: Any, **kwargs: Any) -> None:
        return None

    def insert_one(self, doc: dict[str, Any]) -> None:
        self.docs.append(dict(doc))

    def insert_many(self, docs: list[dict[str, Any]]) -> None:
        for doc in docs:
            self.insert_one(doc)

    def find(self, filt: dict[str, Any] | None = None):
        filt = filt or {}
        return [
            dict(doc)
            for doc in self.docs
            if all(doc.get(key) == value for key, value in filt.items())
        ]

    def delete_many(self, filt: dict[str, Any]) -> None:
        self.docs = [
            doc
            for doc in self.docs
            if not all(doc.get(key) == value for key, value in filt.items())
        ]

    def count_documents(self, filt: dict[str, Any] | None = None) -> int:
        return len(self.find(filt))

    def find_one(self, filt: dict[str, Any]) -> dict[str, Any] | None:
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in filt.items()):
                return dict(doc)
        return None

    def update_one(self, filt: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> None:
        doc = None
        for existing in self.docs:
            if all(existing.get(key) == value for key, value in filt.items()):
                doc = existing
                break
        if doc is None:
            if not upsert:
                return
            doc = dict(filt)
            self.docs.append(doc)
        for key, value in (update.get("$set") or {}).items():
            doc[key] = value
        for key, value in (update.get("$setOnInsert") or {}).items():
            doc.setdefault(key, value)
        for key, value in (update.get("$inc") or {}).items():
            current = doc.get(key) or 0
            doc[key] = current + value


class FakeDB:
    def __init__(self) -> None:
        self._cols: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self._cols:
            self._cols[name] = FakeCollection()
        return self._cols[name]


def make_settings(**kwargs: Any) -> Settings:
    values: dict[str, Any] = {
        "department_id": "starter",
        "jwt_secret": "s" * 32,
        "google_client_id": "",
        "mongo_uri": "disabled",
        "qdrant_url": "disabled",
        "embed_backend": "hash",
        "department_yaml": _API_DIR / "configs" / "department.yaml",
        "persona_yaml": _API_DIR / "configs" / "persona.yaml",
        "ui_dist_dir": Path("/nonexistent-ui-dist"),
    }
    values.update(kwargs)
    return Settings(**values)


def isolated_app(**kwargs: Any):
    return create_app(make_settings(**kwargs))


def fake_google(email: str, sub: str = "google-sub"):
    def _verify(token: str, audience: str) -> dict[str, Any]:
        return {
            "sub": sub,
            "email": email,
            "email_verified": True,
            "aud": audience,
            "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
        }

    return _verify


def logged_in_client(*, email: str, admins: list[str] | None = None, extra_body: dict | None = None) -> TestClient:
    app = isolated_app(google_client_id="test-client.apps.googleusercontent.com")
    app.state.db = FakeDB()
    app.state.mongo_ok = True
    dept = dict(app.state.department or {})
    dept["id"] = dept.get("id") or "starter"
    dept["admins"] = admins or []
    dept.setdefault("rate_limit", {"chats_per_minute": 10, "llm_tokens_per_day": 50000})
    app.state.department = dept
    app.state.verify_google_id_token = fake_google(email)
    client = TestClient(app)
    body = {"id_token": "x" * 40}
    if extra_body:
        body.update(extra_body)
    res = client.post("/api/auth/google", json=body)
    assert res.status_code == 200, res.text
    return client
