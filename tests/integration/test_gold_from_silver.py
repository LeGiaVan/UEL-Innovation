from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.gold.builder import build_gold_chunks
from app.gold.embedder import HashEmbedder, load_embedder
from app.gold.indexer import GoldIndexer
from app.gold.qdrant_store import QdrantGoldStore
from app.repositories.silver import PostgresSilverWriter
from tests.helpers.xlsx_builder import write_mini_release
from tests.integration.test_silver_postgres import _sync

pytestmark = pytest.mark.integration


def test_gold_builds_faq_and_document_chunks_from_silver(
    tmp_path: Path,
    db_session: Session,
    silver_writer: PostgresSilverWriter,
    silver_engine: Engine,
) -> None:
    config_path = write_mini_release(tmp_path / "release")
    outcome = _sync(tmp_path, silver_writer, tmp_path / "release", config_path)
    assert outcome.status == "completed"
    db_session.expire_all()
    chunks = build_gold_chunks(
        db_session,
        department_id="bao_dam_chat_luong",
        module_code="khao_khi",
        environment="test",
    )
    faq_chunks = [item for item in chunks if item.entity_type == "faq"]
    assert len(faq_chunks) == 2
    assert chunks
    assert all("Phòng Bảo đảm chất lượng" in item.stair_markdown for item in chunks)
    assert all("Khảo khí" in item.stair_markdown for item in chunks)
    assert all("support_contact" not in item.payload for item in chunks)
    assert all("phongbdcl@" not in item.stair_markdown for item in chunks)

    embedder = load_embedder("hash-test")
    assert isinstance(embedder, HashEmbedder)
    indexer = GoldIndexer(
        sessionmaker(silver_engine, expire_on_commit=False),
        QdrantGoldStore(QdrantClient(":memory:"), "uel_knowledge_test"),
        embedder,
    )
    stats = indexer.sync(
        department_id="bao_dam_chat_luong",
        module_code="khao_khi",
        environment="test",
        output_dir=tmp_path / "gold",
        full_rebuild=True,
    )
    assert stats.status == "completed"
    assert stats.chunk_count == len(chunks)
    assert stats.upserted_count == len(chunks)
    hits = indexer.search(
        faq_chunks[0].stair_markdown,
        department_id="bao_dam_chat_luong",
        module_code="khao_khi",
        environment="test",
        limit=5,
    )
    assert hits
    assert all(item.payload["department_id"] == "bao_dam_chat_luong" for item in hits)
