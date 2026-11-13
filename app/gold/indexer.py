from __future__ import annotations

import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.gold.builder import build_gold_chunks
from app.gold.embedder import Embedder, load_embedder
from app.gold.models import GoldHit, GoldStats
from app.gold.policy import DEFAULT_FAQ_SCORE_BOOST
from app.gold.qdrant_store import QdrantGoldStore
from app.gold.report import write_gold_markdown
from app.repositories.silver import create_sync_engine


class GoldIndexer:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        store: QdrantGoldStore,
        embedder: Embedder,
        *,
        faq_boost: float = DEFAULT_FAQ_SCORE_BOOST,
    ) -> None:
        self._session_factory = session_factory
        self._store = store
        self._embedder = embedder
        self.faq_boost = faq_boost

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> GoldIndexer:
        resolved = settings or Settings()
        engine = create_sync_engine(resolved)
        client = QdrantClient(
            url=str(resolved.qdrant_url),
            timeout=120,
            check_compatibility=False,
        )
        return cls(
            sessionmaker(engine, expire_on_commit=False),
            QdrantGoldStore(client, resolved.qdrant_collection),
            load_embedder(
                resolved.embedding_model,
                batch_size=resolved.embedding_batch_size,
                max_length=resolved.embedding_max_length,
            ),
            faq_boost=resolved.gold_faq_score_boost,
        )

    def sync(
        self,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        output_dir: Path,
        full_rebuild: bool = False,
    ) -> GoldStats:
        stats = GoldStats(
            collection=self._store.collection,
            model=self._embedder.model_name,
        )
        with self._session_factory() as session:
            chunks = build_gold_chunks(
                session,
                department_id=department_id,
                module_code=module_code,
                environment=environment,
            )
        stats.chunk_count = len(chunks)
        self._store.ensure_collection(self._embedder.dense_dim)
        if full_rebuild:
            stats.deleted_count = self._store.delete_tenant(department_id, module_code)
            to_embed = chunks
        else:
            existing = self._store.existing_hashes([uuid.UUID(chunk.point_id) for chunk in chunks])
            to_embed = [
                chunk for chunk in chunks if existing.get(chunk.chunk_id) != chunk.content_hash
            ]
            stats.unchanged_count = len(chunks) - len(to_embed)
            current_ids = {chunk.point_id for chunk in chunks}
            stale = [
                point_id
                for point_id in self._store.tenant_point_ids(department_id, module_code)
                if point_id not in current_ids
            ]
            self._store.delete_ids(stale)
            stats.deleted_count = len(stale)

        if to_embed:
            print(
                f"gold: {len(chunks)} chunks, embedding {len(to_embed)} "
                f"(collection={self._store.collection})",
                flush=True,
            )
            embeddings = self._embedder.embed([chunk.stair_markdown for chunk in to_embed])
            print(f"gold: upserting {len(to_embed)} points", flush=True)
            self._store.upsert(to_embed, embeddings)
            stats.upserted_count = len(to_embed)
            print("gold: upsert finished", flush=True)
        write_gold_markdown(
            chunks,
            output_dir,
            department_id=department_id,
            module_code=module_code,
            stats=stats,
        )
        stats.status = "completed"
        return stats

    def search(
        self,
        query: str,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        limit: int = 8,
        mode: str = "hybrid",
        faq_boost: float | None = None,
    ) -> list[GoldHit]:
        embedded = self._embedder.embed([query])[0]
        return self._store.search(
            query=embedded,
            department_id=department_id,
            module_code=module_code,
            environment=environment,
            limit=limit,
            faq_boost=self.faq_boost if faq_boost is None else faq_boost,
            mode=mode,
        )


class NullGoldIndexer:
    faq_boost = 0.0

    def sync(
        self,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        output_dir: Path,
        full_rebuild: bool = False,
    ) -> GoldStats:
        del department_id, module_code, environment, output_dir, full_rebuild
        return GoldStats(status="skipped")

    def search(
        self,
        query: str,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        limit: int = 8,
        mode: str = "hybrid",
        faq_boost: float | None = None,
    ) -> list[GoldHit]:
        del query, department_id, module_code, environment, limit, mode, faq_boost
        return []
