from qdrant_client import QdrantClient

from app.gold.embedder import HashEmbedder
from app.gold.ids import gold_chunk_id, point_uuid
from app.gold.models import GoldChunk, GoldEntityType
from app.gold.policy import boosted_score
from app.gold.qdrant_store import QdrantGoldStore
from app.ingestion.normalize import content_hash


def _chunk(
    entity_type: GoldEntityType, key: str, body: str, department: str = "bao_dam_chat_luong"
) -> GoldChunk:
    chunk_id = gold_chunk_id(department, "khao_khi", entity_type, key)
    markdown = f"# {body}\n\n- Phòng ban: Phòng Bảo đảm chất lượng\n- Mô-đun: Khảo khí\n"
    return GoldChunk(
        chunk_id=chunk_id,
        point_id=str(point_uuid(chunk_id)),
        entity_type=entity_type,
        stair_markdown=markdown,
        content_hash=content_hash(markdown),
        payload={
            "chunk_id": chunk_id,
            "department_id": department,
            "module_code": "khao_khi",
            "entity_type": entity_type,
            "is_active": True,
            "release_status": "approved_for_dev",
            "content_hash": content_hash(markdown),
            "stair_markdown": markdown,
            "effective_from": None,
            "effective_to": None,
        },
    )


def test_hybrid_search_hard_filters_department_and_boosts_faq() -> None:
    store = QdrantGoldStore(QdrantClient(":memory:"), "uel_knowledge_test")
    embedder = HashEmbedder()
    faq = _chunk("faq", "I.1.001", "thoi han phuc khao dhcq hai ngay")
    doc = _chunk("regulation", "TL01-phone", "thoi han phuc khao dhcq hai ngay")
    leaked = _chunk("faq", "other", "thoi han phuc khao dhcq hai ngay", department="other_dept")
    chunks = [faq, doc, leaked]
    store.ensure_collection(embedder.dense_dim)
    store.upsert(chunks, embedder.embed([item.stair_markdown for item in chunks]))
    query = embedder.embed([faq.stair_markdown])[0]
    hits = store.search(
        query=query,
        department_id="bao_dam_chat_luong",
        module_code="khao_khi",
        environment="test",
        limit=5,
        faq_boost=0.12,
    )
    assert hits
    assert all(item.payload["department_id"] == "bao_dam_chat_luong" for item in hits)
    assert {item.entity_type for item in hits} >= {"faq", "regulation"}
    faq_hit = next(item for item in hits if item.entity_type == "faq")
    assert faq_hit.boosted_score == boosted_score("faq", faq_hit.score, 0.12)


def test_incremental_upsert_skips_unchanged_and_deletes_stale() -> None:
    store = QdrantGoldStore(QdrantClient(":memory:"), "uel_knowledge_test")
    embedder = HashEmbedder()
    first = _chunk("faq", "I.1.001", "cau hoi mot")
    stale = _chunk("faq", "I.1.099", "cau hoi cu")
    store.ensure_collection(embedder.dense_dim)
    store.upsert([first, stale], embedder.embed([first.stair_markdown, stale.stair_markdown]))
    existing = store.existing_hashes([point_uuid(first.chunk_id), point_uuid(stale.chunk_id)])
    assert existing[first.chunk_id] == first.content_hash
    updated = _chunk("faq", "I.1.001", "cau hoi mot da sua")
    store.upsert([updated], embedder.embed([updated.stair_markdown]))
    current_ids = {updated.point_id}
    stale_ids = [
        point_id
        for point_id in store.tenant_point_ids("bao_dam_chat_luong", "khao_khi")
        if point_id not in current_ids
    ]
    store.delete_ids(stale_ids)
    remaining = set(store.tenant_point_ids("bao_dam_chat_luong", "khao_khi"))
    assert remaining == {updated.point_id}
