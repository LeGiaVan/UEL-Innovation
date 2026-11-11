from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AnswerStatus = Literal[
    "faq_answered",
    "answered",
    "greeting",
    "human_handoff",
    "out_of_scope",
    "insufficient_evidence",
    "clarification_required",
    "error",
]
RoutingScope = Literal["answer_allowed", "human_required", "out_of_scope"]
TrainingSystem = Literal["dhcq", "sdh", "vb2_vlvh", "unknown"]
AgentTopic = Literal[
    "phuc_khao",
    "diem_i_nhan",
    "diem_i_tra",
    "seb",
    "hinh_thuc_thi",
    "fee",
    "other",
]


class Citation(BaseModel):
    kind: Literal["question_code", "document_code", "chunk_id"]
    value: str


class ChatResult(BaseModel):
    request_id: str
    status: AnswerStatus
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    routing_scope: str | None = None
    routing_source: str | None = None
    rule_id: str | None = None
    rule_version: str | None = None
    support_contact: str | None = None
    contact_information: str | None = None
    online_channel: str | None = None
    node_latency_ms: dict[str, float] = Field(default_factory=dict)
    llm_calls: list[str] = Field(default_factory=list)
    search_called: bool = False
    generate_called: bool = False
    faq_question_code: str | None = None
    error_message: str | None = None


class FaqMatch(BaseModel):
    question_code: str
    question: str
    answer: str
    legal_basis: str | None = None


class RetrievedEvidence(BaseModel):
    chunk_id: str
    entity_type: str
    document_code: str | None = None
    question_code: str | None = None
    boosted_score: float
    stair_markdown: str
    fee_type: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
