from __future__ import annotations

from pathlib import Path

from app.gold.models import GoldChunk, GoldStats


def write_gold_markdown(
    chunks: list[GoldChunk],
    output_dir: Path,
    *,
    department_id: str,
    module_code: str,
    stats: GoldStats,
) -> Path:
    target = output_dir / department_id / module_code
    target.mkdir(parents=True, exist_ok=True)
    index_lines = [
        f"# Gold chunks — {department_id}/{module_code}",
        "",
        f"- collection: {stats.collection}",
        f"- model: {stats.model}",
        f"- chunks: {len(chunks)}",
        f"- upserted: {stats.upserted_count}",
        f"- unchanged: {stats.unchanged_count}",
        f"- deleted: {stats.deleted_count}",
        "",
        "| chunk_id | entity_type |",
        "|---|---|",
    ]
    for chunk in chunks:
        stem = chunk.chunk_id.replace(":", "_")
        (target / f"{stem}.md").write_text(chunk.stair_markdown, encoding="utf-8")
        index_lines.append(f"| `{chunk.chunk_id}` | {chunk.entity_type} |")
    index_path = target / "index.md"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    return index_path
