from __future__ import annotations

import logging
import uuid
from typing import Any

log = logging.getLogger(__name__)


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return float(sum(a[i] * b[i] for i in range(n)))


def _match(point: dict[str, Any], filt: dict[str, Any] | None) -> bool:
    if not filt:
        return True
    for key, value in filt.items():
        if isinstance(value, (list, tuple, set, frozenset)):
            if point.get(key) not in value:
                return False
        elif point.get(key) != value:
            return False
    return True


COL_RULES = "rules"
COL_DOCS = "docs"


class MemoryQdrant:
    def __init__(self) -> None:
        self.rules: list[dict[str, Any]] = []
        self.docs: list[dict[str, Any]] = []

    def ensure_collections(self, dim: int = 1024) -> None:
        return None

    def set_payload(self, collection: str, point_id: str, payload: dict[str, Any]) -> None:
        bucket = self.rules if collection == COL_RULES else self.docs
        for point in bucket:
            if str(point.get("id")) == str(point_id):
                point.update(payload)
                return

    def upsert(self, collection: str, points: list[dict[str, Any]]) -> None:
        bucket = self.rules if collection == COL_RULES else self.docs
        ids = {p["id"] for p in points}
        remain = [p for p in bucket if p["id"] not in ids]
        remain.extend(points)
        if collection == COL_RULES:
            self.rules = remain
        else:
            self.docs = remain

    def wipe(self) -> None:
        self.rules = []
        self.docs = []

    def search(
        self,
        collection: str,
        vector: list[float],
        *,
        limit: int = 6,
        filt: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        bucket = self.rules if collection == COL_RULES else self.docs
        ranked = []
        for point in bucket:
            if not _match(point, filt):
                continue
            ranked.append({**point, "score": _cosine(vector, point.get("vector") or [])})
        ranked.sort(key=lambda p: p["score"], reverse=True)
        return ranked[: max(1, limit)]

    def scroll(self, collection: str, *, filt: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        bucket = self.rules if collection == COL_RULES else self.docs
        return [dict(p) for p in bucket if _match(p, filt)]

    def delete_release(self, collection: str, *, module_code: str, release_id: str) -> None:
        bucket = self.rules if collection == COL_RULES else self.docs
        kept = [
            p
            for p in bucket
            if not (p.get("module_code") == module_code and p.get("release_id") == release_id)
        ]
        if collection == COL_RULES:
            self.rules = kept
        else:
            self.docs = kept


class QdrantStore:
    def __init__(self, url: str, dim: int = 1024) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http.exceptions import UnexpectedResponse
        from qdrant_client.models import Distance, VectorParams

        self.dim = dim
        self.client = QdrantClient(url=url, timeout=20, check_compatibility=False)
        self.client.get_collections()
        for name in (COL_RULES, COL_DOCS):
            try:
                self.client.get_collection(name)
            except (UnexpectedResponse, Exception):
                self.client.recreate_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                )

    def ensure_collections(self, dim: int = 1024) -> None:
        return None

    def upsert(self, collection: str, points: list[dict[str, Any]]) -> None:
        from qdrant_client.models import PointStruct

        structs = [
            PointStruct(id=p["id"], vector=p["vector"], payload={k: v for k, v in p.items() if k not in {"id", "vector"}})
            for p in points
        ]
        if structs:
            self.client.upsert(collection_name=collection, points=structs)

    def set_payload(self, collection: str, point_id: str, payload: dict[str, Any]) -> None:
        self.client.set_payload(
            collection_name=collection,
            payload=payload,
            points=[point_id],
            wait=True,
        )

    def search(
        self,
        collection: str,
        vector: list[float],
        *,
        limit: int = 6,
        filt: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

        must = []
        for key, value in (filt or {}).items():
            if isinstance(value, (list, tuple, set, frozenset)):
                must.append(FieldCondition(key=key, match=MatchAny(any=list(value))))
            else:
                must.append(FieldCondition(key=key, match=MatchValue(value=value)))
        query_filter = Filter(must=must) if must else None
        if hasattr(self.client, "query_points"):
            res = self.client.query_points(
                collection_name=collection,
                query=vector,
                limit=max(1, limit),
                query_filter=query_filter,
                with_payload=True,
            )
            hits = res.points
        else:
            hits = self.client.search(
                collection_name=collection,
                query_vector=vector,
                limit=max(1, limit),
                query_filter=query_filter,
                with_payload=True,
            )
        out = []
        for hit in hits:
            payload = dict(hit.payload or {})
            payload["id"] = str(hit.id)
            payload["score"] = float(hit.score or 0)
            out.append(payload)
        return out

    def scroll(self, collection: str, *, filt: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

        must = []
        for key, value in (filt or {}).items():
            if isinstance(value, (list, tuple, set, frozenset)):
                must.append(FieldCondition(key=key, match=MatchAny(any=list(value))))
            else:
                must.append(FieldCondition(key=key, match=MatchValue(value=value)))
        records, _ = self.client.scroll(
            collection_name=collection,
            scroll_filter=Filter(must=must) if must else None,
            limit=256,
            with_payload=True,
        )
        out = []
        for rec in records:
            payload = dict(rec.payload or {})
            payload["id"] = str(rec.id)
            out.append(payload)
        return out

    def wipe(self) -> None:
        from qdrant_client.models import Distance, VectorParams

        for name in (COL_RULES, COL_DOCS):
            self.client.recreate_collection(
                collection_name=name,
                vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
            )

    def delete_release(self, collection: str, *, module_code: str, release_id: str) -> None:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        self.client.delete(
            collection_name=collection,
            points_selector=Filter(
                must=[
                    FieldCondition(key="module_code", match=MatchValue(value=module_code)),
                    FieldCondition(key="release_id", match=MatchValue(value=release_id)),
                ]
            ),
        )


def connect_qdrant(url: str, dim: int = 1024) -> QdrantStore | None:
    if not url or url.strip().lower() in {"disabled", "none", "off"}:
        return None
    try:
        return QdrantStore(url, dim=dim)
    except Exception as exc:  # noqa: BLE001
        log.warning("Qdrant not ready: %s", exc)
        return None


def point_id(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "|".join(parts)))
