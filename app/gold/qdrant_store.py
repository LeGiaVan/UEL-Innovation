from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    Fusion,
    FusionQuery,
    MatchValue,
    PayloadSchemaType,
    PointIdsList,
    PointStruct,
    Prefetch,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.gold.models import EmbeddedText, GoldChunk, GoldHit
from app.gold.policy import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    allowed_release_statuses,
    boosted_score,
    is_effective,
)

PAYLOAD_INDEXES = (
    "department_id",
    "module_code",
    "entity_type",
    "release_status",
    "document_code",
    "is_active",
)


class QdrantGoldStore:
    def __init__(self, client: QdrantClient, collection: str) -> None:
        self._client = client
        self.collection = collection

    def ensure_collection(self, dense_dim: int) -> None:
        if self._client.collection_exists(self.collection):
            return
        self._client.create_collection(
            collection_name=self.collection,
            vectors_config={
                DENSE_VECTOR_NAME: VectorParams(size=dense_dim, distance=Distance.COSINE)
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: SparseVectorParams(index=SparseIndexParams(on_disk=False))
            },
        )
        for field in PAYLOAD_INDEXES:
            schema = PayloadSchemaType.BOOL if field == "is_active" else PayloadSchemaType.KEYWORD
            self._client.create_payload_index(
                collection_name=self.collection,
                field_name=field,
                field_schema=schema,
            )

    def existing_hashes(self, point_ids: list[uuid.UUID]) -> dict[str, str]:
        if not point_ids:
            return {}
        records = self._client.retrieve(
            collection_name=self.collection,
            ids=list(point_ids),
            with_payload=["content_hash", "chunk_id"],
        )
        hashes: dict[str, str] = {}
        for record in records:
            payload = record.payload or {}
            chunk_id = str(payload.get("chunk_id") or "")
            content_hash = str(payload.get("content_hash") or "")
            if chunk_id:
                hashes[chunk_id] = content_hash
        return hashes

    def upsert(self, chunks: list[GoldChunk], embeddings: list[EmbeddedText]) -> None:
        points = [
            PointStruct(
                id=chunk.point_id,
                vector={
                    DENSE_VECTOR_NAME: embedding.dense,
                    SPARSE_VECTOR_NAME: SparseVector(
                        indices=embedding.sparse_indices,
                        values=embedding.sparse_values,
                    ),
                },
                payload=chunk.payload,
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        if points:
            self._client.upsert(collection_name=self.collection, points=points)

    def tenant_payloads(self, department_id: str, module_code: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        offset: Any = None
        while True:
            records, offset = self._client.scroll(
                collection_name=self.collection,
                scroll_filter=_tenant_filter(department_id, module_code),
                limit=128,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                found.append(dict(record.payload or {}))
            if offset is None:
                break
        return found

    def tenant_point_ids(self, department_id: str, module_code: str) -> list[str]:
        found: list[str] = []
        offset: Any = None
        while True:
            records, offset = self._client.scroll(
                collection_name=self.collection,
                scroll_filter=_tenant_filter(department_id, module_code),
                limit=128,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            found.extend(str(record.id) for record in records)
            if offset is None:
                break
        return found

    def delete_ids(self, point_ids: list[str]) -> None:
        if not point_ids:
            return
        self._client.delete(
            collection_name=self.collection,
            points_selector=PointIdsList(points=point_ids),
        )

    def delete_tenant(self, department_id: str, module_code: str) -> int:
        ids = self.tenant_point_ids(department_id, module_code)
        self._client.delete(
            collection_name=self.collection,
            points_selector=FilterSelector(filter=_tenant_filter(department_id, module_code)),
        )
        return len(ids)

    def search(
        self,
        *,
        query: EmbeddedText,
        department_id: str,
        module_code: str,
        environment: str,
        limit: int,
        faq_boost: float,
        mode: str = "hybrid",
    ) -> list[GoldHit]:
        prefetch_limit = max(limit * 4, 20)
        query_filter = Filter(
            must=[
                FieldCondition(key="department_id", match=MatchValue(value=department_id)),
                FieldCondition(key="module_code", match=MatchValue(value=module_code)),
                FieldCondition(key="is_active", match=MatchValue(value=True)),
            ]
        )
        try:
            if mode == "dense":
                results = self._client.query_points(
                    collection_name=self.collection,
                    query=query.dense,
                    using=DENSE_VECTOR_NAME,
                    query_filter=query_filter,
                    limit=prefetch_limit,
                    with_payload=True,
                )
            else:
                results = self._client.query_points(
                    collection_name=self.collection,
                    prefetch=[
                        Prefetch(
                            query=query.dense,
                            using=DENSE_VECTOR_NAME,
                            limit=prefetch_limit,
                            filter=query_filter,
                        ),
                        Prefetch(
                            query=SparseVector(
                                indices=query.sparse_indices, values=query.sparse_values
                            ),
                            using=SPARSE_VECTOR_NAME,
                            limit=prefetch_limit,
                            filter=query_filter,
                        ),
                    ],
                    query=FusionQuery(fusion=Fusion.RRF),
                    query_filter=query_filter,
                    limit=prefetch_limit,
                    with_payload=True,
                )
            points = results.points
        except (UnexpectedResponse, ValueError):
            results = self._client.query_points(
                collection_name=self.collection,
                query=query.dense,
                using=DENSE_VECTOR_NAME,
                query_filter=query_filter,
                limit=prefetch_limit,
                with_payload=True,
            )
            points = results.points

        allowed = allowed_release_statuses(environment)
        hits: list[GoldHit] = []
        for point in points:
            payload = dict(point.payload or {})
            if payload.get("release_status") not in allowed:
                continue
            if not is_effective(payload):
                continue
            entity_type = str(payload.get("entity_type") or "")
            score = float(point.score or 0.0)
            boosted = boosted_score(entity_type, score, faq_boost)
            hits.append(
                GoldHit(
                    chunk_id=str(payload.get("chunk_id") or ""),
                    entity_type=entity_type,
                    score=score,
                    boosted_score=boosted,
                    stair_markdown=str(payload.get("stair_markdown") or ""),
                    payload=payload,
                )
            )
        hits.sort(key=lambda item: item.boosted_score, reverse=True)
        return hits[:limit]


def _tenant_filter(department_id: str, module_code: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(key="department_id", match=MatchValue(value=department_id)),
            FieldCondition(key="module_code", match=MatchValue(value=module_code)),
        ]
    )
