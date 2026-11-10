from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

GoldEntityType = Literal["faq", "regulation", "condition", "procedure", "dossier", "step"]


class GoldChunk(BaseModel):
    chunk_id: str
    point_id: str
    entity_type: GoldEntityType
    stair_markdown: str
    content_hash: str
    payload: dict[str, Any]


class EmbeddedText(BaseModel):
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]


class GoldStats(BaseModel):
    status: Literal["completed", "skipped", "failed"] = "completed"
    collection: str = ""
    model: str = ""
    upserted_count: int = 0
    unchanged_count: int = 0
    deleted_count: int = 0
    chunk_count: int = 0
    error_message: str | None = None


class GoldHit(BaseModel):
    chunk_id: str
    entity_type: str
    score: float
    boosted_score: float
    stair_markdown: str
    payload: dict[str, Any] = Field(default_factory=dict)
