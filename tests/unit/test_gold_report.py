from pathlib import Path

from app.gold.ids import gold_chunk_id, point_uuid
from app.gold.models import GoldChunk, GoldStats
from app.gold.report import write_gold_markdown
from app.ingestion.normalize import content_hash


def test_write_gold_markdown_index(tmp_path: Path) -> None:
    chunk_id = gold_chunk_id("bao_dam_chat_luong", "khao_khi", "faq", "I.1.001")
    markdown = "# Câu hỏi\n"
    chunk = GoldChunk(
        chunk_id=chunk_id,
        point_id=str(point_uuid(chunk_id)),
        entity_type="faq",
        stair_markdown=markdown,
        content_hash=content_hash(markdown),
        payload={},
    )
    stats = GoldStats(collection="uel_knowledge_test", model="hash-test", chunk_count=1)
    index = write_gold_markdown(
        [chunk],
        tmp_path,
        department_id="bao_dam_chat_luong",
        module_code="khao_khi",
        stats=stats,
    )
    assert index.is_file()
    assert "faq" in index.read_text(encoding="utf-8")
    stem = chunk_id.replace(":", "_")
    assert (tmp_path / "bao_dam_chat_luong" / "khao_khi" / f"{stem}.md").is_file()
