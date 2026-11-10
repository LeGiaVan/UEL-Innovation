from __future__ import annotations

import time
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.gold.indexer import GoldIndexer
from app.gold.models import GoldHit
from app.ingestion.normalize import extract_emails, extract_hotlines

_SECRET_MARKERS = ("api_key", "password", "secret")


class SmokeCase(BaseModel):
    query: str
    expect_any: list[str] = Field(default_factory=list)


class SmokeResult(BaseModel):
    query: str
    hit_count: int
    top_entity: str | None
    top_preview: str
    expect_matched: bool
    departments: list[str]


class GoldVerifyReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    collection: str
    model: str
    point_count: int
    entity_counts: dict[str, int]
    release_statuses: dict[str, int]
    pii_hits: int
    tenant_leak_hits: int
    incremental_unchanged: int
    incremental_upserted: int
    dense_dim: int
    query_embed_seconds: float | None = None
    smoke: list[SmokeResult] = Field(default_factory=list)


SMOKE_CASES: tuple[SmokeCase, ...] = (
    SmokeCase(query="Thời hạn phúc khảo đại học chính quy", expect_any=["2 ngày", "phúc khảo"]),
    SmokeCase(query="Thời hạn phúc khảo sau đại học", expect_any=["7 ngày", "SĐH", "sau đại học"]),
    SmokeCase(query="Thời hạn nộp đơn nhận điểm I", expect_any=["3 ngày", "điểm I", "TL03"]),
    SmokeCase(
        query="Đăng ký trả điểm I trước đợt thi bổ sung", expect_any=["7 ngày", "điểm I", "TL04"]
    ),
    SmokeCase(query="Mang điện thoại vào phòng thi", expect_any=["điện thoại", "phòng thi"]),
    SmokeCase(
        query="Lệ phí phúc khảo bao nhiêu",
        expect_any=["chưa xác định", "không nêu số tiền", "lệ phí"],
    ),
)


def payload_has_pii(payload: dict[str, Any]) -> bool:
    blob = str(payload.get("stair_markdown") or "")
    if extract_emails(blob) or extract_hotlines(blob):
        return True
    lowered = blob.casefold()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def count_entities(payloads: Sequence[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(item.get("entity_type") or "unknown") for item in payloads))


def count_release_statuses(payloads: Sequence[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(item.get("release_status") or "unknown") for item in payloads))


def run_gold_verify(
    indexer: GoldIndexer,
    *,
    department_id: str,
    module_code: str,
    environment: str,
    output_dir: Path,
) -> GoldVerifyReport:
    incremental = indexer.sync(
        department_id=department_id,
        module_code=module_code,
        environment=environment,
        output_dir=output_dir,
        full_rebuild=False,
    )
    payloads = indexer._store.tenant_payloads(department_id, module_code)
    leak_hits = indexer.search(
        "Thời hạn phúc khảo",
        department_id="other_department",
        module_code=module_code,
        environment=environment,
        limit=5,
    )
    smoke: list[SmokeResult] = []
    query_embed_seconds: float | None = None
    for index, case in enumerate(SMOKE_CASES):
        mark = time.perf_counter()
        hits = indexer.search(
            case.query,
            department_id=department_id,
            module_code=module_code,
            environment=environment,
            limit=5,
        )
        if index == 0:
            query_embed_seconds = round(time.perf_counter() - mark, 3)
        smoke.append(_smoke_result(case, hits))
    return GoldVerifyReport(
        collection=indexer._store.collection,
        model=indexer._embedder.model_name,
        point_count=len(payloads),
        entity_counts=count_entities(payloads),
        release_statuses=count_release_statuses(payloads),
        pii_hits=sum(1 for item in payloads if payload_has_pii(item)),
        tenant_leak_hits=len(leak_hits),
        incremental_unchanged=incremental.unchanged_count,
        incremental_upserted=incremental.upserted_count,
        dense_dim=indexer._embedder.dense_dim,
        query_embed_seconds=query_embed_seconds,
        smoke=smoke,
    )


def _smoke_result(case: SmokeCase, hits: Sequence[GoldHit]) -> SmokeResult:
    preview = hits[0].stair_markdown if hits else ""
    haystack = " ".join(hit.stair_markdown for hit in hits).casefold()
    matched = not case.expect_any or any(token.casefold() in haystack for token in case.expect_any)
    departments = sorted(
        {
            str(hit.payload.get("department_id") or "")
            for hit in hits
            if hit.payload.get("department_id")
        }
    )
    return SmokeResult(
        query=case.query,
        hit_count=len(hits),
        top_entity=hits[0].entity_type if hits else None,
        top_preview=preview[:240].replace("\n", " "),
        expect_matched=matched,
        departments=departments,
    )
