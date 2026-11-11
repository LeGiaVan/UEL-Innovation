"""Audit extractive responses against indexed Qdrant chunks."""

import json
import os
from pathlib import Path

from qdrant_client import QdrantClient

from app.agent.prompts import readable_stair_excerpt
from app.core.config import Settings


def main():
    expanded = os.getenv("PHASE8_FULL_REVIEW") == "1"
    filename = "phase-08-answer-expanded.json" if expanded else "phase-08-answer-sample.json"
    results = json.loads((Path("reports/phases") / filename).read_text(encoding="utf-8"))
    client = QdrantClient(url="http://127.0.0.1:6333", timeout=60)
    settings = Settings()
    records, offset = [], None
    while True:
        batch, offset = client.scroll(
            settings.qdrant_collection,
            offset=offset,
            limit=128,
            with_payload=True,
            with_vectors=False,
        )
        records.extend(batch)
        if offset is None:
            break
    by_chunk = {str(item.payload.get("chunk_id")): item.payload for item in records if item.payload}
    audits = []
    for case in results:
        if not case["provider_error"]:
            continue
        chunks = [x["value"] for x in case["citations"] if x["kind"] == "chunk_id"]
        matches = []
        labels = set()
        for chunk in chunks:
            payload = by_chunk[chunk]
            if (
                payload.get("department_id") != settings.app_department_id
                or payload.get("module_code") != settings.app_module_code
            ):
                raise RuntimeError("unexpected tenant")
            label = payload.get("document_code") or payload.get("question_code") or "nguon"
            excerpt = readable_stair_excerpt(payload["stair_markdown"])
            matches.append(f"[{label}] {excerpt}" in case["answer"])
            for key in ("document_code", "question_code"):
                if payload.get(key):
                    labels.add(payload[key])
        cited_labels = {x["value"] for x in case["citations"] if x["kind"] != "chunk_id"}
        audits.append(
            {
                "id": case["id"],
                "chunks": len(chunks),
                "all_excerpts_match": bool(chunks) and all(matches),
                "all_labels_match": labels == cited_labels,
            }
        )
    out = {"scope": "extractive fallback only", "cases": audits}
    filename = "phase-08-extractive-expanded.json" if expanded else "phase-08-extractive-audit.json"
    (Path("reports/phases") / filename).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    if not all(x["all_excerpts_match"] and x["all_labels_match"] for x in audits):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
