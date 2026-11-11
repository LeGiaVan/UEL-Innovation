from __future__ import annotations

import re
from typing import Literal

from app.agent.models import Citation, RetrievedEvidence
from app.gold.models import GoldHit

DOCUMENT_CODE_RE = re.compile(r"\bTL0?\d+\b", re.IGNORECASE)
QUESTION_CODE_RE = re.compile(r"\b(?:I|II|III)\.\d+\.\d{3}\b")
CHUNK_ID_RE = re.compile(r"\bgold:[0-9a-f]{24}\b", re.IGNORECASE)


def evidence_from_hit(hit: GoldHit) -> RetrievedEvidence:
    payload = hit.payload
    fee = payload.get("fee_type")
    fee_type = str(fee) if fee else None
    if fee_type is None and "chưa xác định" in hit.stair_markdown.casefold():
        if any(token in hit.stair_markdown.casefold() for token in ("lệ phí", "le phi", "phí")):
            fee_type = "unknown"
    return RetrievedEvidence(
        chunk_id=hit.chunk_id,
        entity_type=hit.entity_type,
        document_code=_optional(payload.get("document_code")),
        question_code=_optional(payload.get("question_code")),
        boosted_score=hit.boosted_score,
        stair_markdown=hit.stair_markdown,
        fee_type=fee_type,
        payload=payload,
    )


def allowed_citation_values(evidence: list[RetrievedEvidence]) -> set[str]:
    values: set[str] = set()
    for item in evidence:
        if item.chunk_id:
            values.add(item.chunk_id.lower())
        if item.document_code:
            values.add(item.document_code.upper())
        if item.question_code:
            values.add(item.question_code)
    return values


def extract_citations(text: str, evidence: list[RetrievedEvidence] | None = None) -> list[Citation]:
    found: list[Citation] = []
    seen: set[str] = set()

    def add(kind: Literal["document_code", "question_code", "chunk_id"], value: str) -> None:
        key = f"{kind}:{value.casefold()}"
        if key not in seen:
            seen.add(key)
            found.append(Citation(kind=kind, value=value))

    for match in DOCUMENT_CODE_RE.findall(text):
        add("document_code", match.upper())
    for match in QUESTION_CODE_RE.findall(text):
        add("question_code", match)
    for match in CHUNK_ID_RE.findall(text):
        add("chunk_id", match.lower())
    for item in evidence or []:
        if item.document_code and _token_in_text(text, item.document_code):
            add("document_code", item.document_code.upper())
        if item.question_code and _token_in_text(text, item.question_code):
            add("question_code", item.question_code)
        if item.chunk_id and _token_in_text(text, item.chunk_id):
            add("chunk_id", item.chunk_id.lower())
    return found


def citations_from_evidence(evidence: list[RetrievedEvidence]) -> list[Citation]:
    found: list[Citation] = []
    seen: set[str] = set()
    for item in evidence:
        if item.document_code:
            value = item.document_code.upper()
            if value not in seen:
                seen.add(value)
                found.append(Citation(kind="document_code", value=value))
        if item.question_code and item.question_code not in seen:
            seen.add(item.question_code)
            found.append(Citation(kind="question_code", value=item.question_code))
        chunk = item.chunk_id.lower()
        if chunk and chunk not in seen:
            seen.add(chunk)
            found.append(Citation(kind="chunk_id", value=item.chunk_id))
    return found


def citations_are_valid(text: str, evidence: list[RetrievedEvidence]) -> bool:
    extracted = extract_citations(text, evidence)
    if not extracted or not evidence:
        return False
    allowed = allowed_citation_values(evidence)
    for item in extracted:
        candidate = item.value.upper() if item.kind == "document_code" else item.value
        if item.kind == "chunk_id":
            candidate = item.value.lower()
        if candidate not in allowed and item.value not in allowed:
            return False
    return True


def _token_in_text(text: str, token: str) -> bool:
    cleaned = token.strip()
    if len(cleaned) < 2:
        return False
    pattern = rf"(?<![\w./-]){re.escape(cleaned)}(?![\w./-])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
