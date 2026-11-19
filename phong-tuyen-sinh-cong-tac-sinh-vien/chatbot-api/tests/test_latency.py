from __future__ import annotations

import statistics
import time
from pathlib import Path

from app.integrations.embeddings import hash_embed
from tests.test_gold_chat import GOLD_PATH, SEED_FILES, _chat, _gold_client, _seed_pack
from app.services.ingest_service import ingest_module
import yaml

GATES_MS = {
    "faq_exact": 2000,
    "no_rag": 3000,
    "rag": 15000,
    "embed": 2000,
}


def _p95(samples: list[float]) -> float:
    if len(samples) == 1:
        return samples[0]
    return float(statistics.quantiles(samples, n=20)[18])


def test_p95_hash_gates(tmp_path: Path) -> None:
    client = _gold_client(tmp_path)
    ingest_module(
        db=client.app.state.db,
        qdrant=client.app.state.qdrant,
        data_dir=tmp_path,
        department=client.app.state.department,
        module_code="khao_khi",
        files=_seed_pack(),
        filenames={i: name for i, name in SEED_FILES.items()},
        embed_dim=1024,
        embed_backend="hash",
    )
    hash_embed(["warmup câu tiếng Việt"])
    embed_samples = []
    for _ in range(21):
        start = time.perf_counter()
        hash_embed(["Một câu hỏi khảo thí để đo embed."])
        embed_samples.append((time.perf_counter() - start) * 1000)
    faq_q = "Người học xem điểm học phần ở đâu?"
    handoff_q = "Kết quả phúc khảo của tôi tuần này ra sao?"
    rag_q = "thời hạn phúc khảo ĐHCQ"
    _chat(client, faq_q, "khao_khi")
    _chat(client, handoff_q, "khao_khi")
    _chat(client, rag_q, "khao_khi")
    faq_ms, no_rag_ms, rag_ms = [], [], []
    for _ in range(12):
        start = time.perf_counter()
        done = _chat(client, faq_q, "khao_khi")
        faq_ms.append((time.perf_counter() - start) * 1000)
        assert done["routing_source"] == "faq_exact"
        start = time.perf_counter()
        done = _chat(client, handoff_q, "khao_khi")
        no_rag_ms.append((time.perf_counter() - start) * 1000)
        assert done["status"] == "human_handoff"
        start = time.perf_counter()
        done = _chat(client, rag_q, "khao_khi")
        rag_ms.append((time.perf_counter() - start) * 1000)
        assert done["routing_source"] == "regex"
    rows = {
        "embed_p95_ms": round(_p95(embed_samples), 1),
        "faq_p95_ms": round(_p95(faq_ms), 1),
        "no_rag_p95_ms": round(_p95(no_rag_ms), 1),
        "rag_no_llm_p95_ms": round(_p95(rag_ms), 1),
        "backend": "hash",
    }
    GOLD_PATH.with_name("latency.last.json").write_text(
        yaml.safe_dump(rows, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    assert rows["embed_p95_ms"] <= GATES_MS["embed"]
    assert rows["faq_p95_ms"] <= GATES_MS["faq_exact"]
    assert rows["no_rag_p95_ms"] <= GATES_MS["no_rag"]
    assert rows["rag_no_llm_p95_ms"] <= GATES_MS["rag"]
