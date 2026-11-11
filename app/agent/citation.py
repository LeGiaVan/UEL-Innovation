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


def answer_distorts_training_labels(
    text: str,
    evidence: list[RetrievedEvidence],
    *,
    training_systems: list[str] | None = None,
) -> bool:
    folded = text.casefold()
    if "sinh viên học kỳ" in folded or "sinh vien hoc ky" in folded:
        return True
    if "đại học chính chính" in folded:
        return True
    source = " ".join(item.stair_markdown for item in evidence).casefold()
    asked = [item for item in (training_systems or []) if item]
    mentions_sdh = "sđh" in folded or "sau đại học" in folded or "cao học" in folded
    if "sinh viên đại học" in folded and "sau đại học" not in folded:
        if "sđh" in source or "sau đại học" in source or "sdh" in asked:
            return True
    if "sdh" in asked and not mentions_sdh:
        if "sinh viên đại học" in folded or "đại học chính quy" in folded:
            return True
    if len(asked) >= 2:
        has_dhcq = "đhcq" in folded or "dhcq" in folded or "đại học chính quy" in folded
        has_sdh = mentions_sdh or "sdh" in folded
        if "dhcq" in asked and "sdh" in asked and not (has_dhcq and has_sdh):
            return True
    return False


def citations_are_valid(text: str, evidence: list[RetrievedEvidence]) -> bool:
    extracted = extract_citations(text, evidence)
    if not extracted or not evidence:
        return False
    return not has_invented_citations(extracted, evidence)


def has_invented_citations(
    extracted: list[Citation], evidence: list[RetrievedEvidence]
) -> bool:
    if not extracted:
        return False
    allowed = allowed_citation_values(evidence)
    for item in extracted:
        candidate = item.value.upper() if item.kind == "document_code" else item.value
        if item.kind == "chunk_id":
            candidate = item.value.lower()
        if candidate not in allowed and item.value not in allowed:
            return True
    return False


_STOPWORDS = frozenset(
    {
        "theo",
        "hoặc",
        "được",
        "trong",
        "những",
        "rằng",
        "này",
        "các",
        "của",
        "với",
        "cho",
        "không",
        "và",
        "là",
        "một",
        "cũng",
        "như",
        "khi",
        "còn",
        "nên",
        "đã",
        "sẽ",
        "vào",
        "từ",
        "trên",
        "dưới",
        "bạn",
        "mình",
        "người",
        "học",
        "rồi",
        "nữa",
        "only",
        "with",
        "from",
        "that",
        "this",
        "have",
        "been",
    }
)
_TOKEN_RE = re.compile(
    r"[0-9a-zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]+",
    re.IGNORECASE,
)
_SOURCE_HEADING_RE = re.compile(
    r"(?i)^\s*(?:\*{0,2}|#{1,3}\s*)mã nguồn(?: tham khảo)?\s*:?\s*\*{0,2}\s*$"
)


def answer_overlaps_evidence(text: str, evidence: list[RetrievedEvidence]) -> bool:
    if not evidence:
        return False
    source = " ".join(item.stair_markdown for item in evidence).casefold()
    tokens = [
        token
        for token in _TOKEN_RE.findall(text.casefold())
        if len(token) >= 4 and token not in _STOPWORDS
    ]
    if not tokens:
        return False
    hits = sum(1 for token in tokens if token in source)
    return hits >= min(2, len(tokens))


def student_facing_answer(text: str) -> str:
    lines: list[str] = []
    skipping_gold_section = False
    for raw in text.replace("\r\n", "\n").split("\n"):
        if _SOURCE_HEADING_RE.match(raw):
            skipping_gold_section = True
            continue
        if skipping_gold_section:
            if CHUNK_ID_RE.search(raw) or re.match(r"(?i)^\s*[-*]\s*mã:", raw):
                continue
            if not raw.strip():
                continue
            skipping_gold_section = False
        cleaned = CHUNK_ID_RE.sub("", raw)
        cleaned = re.sub(r"(?i)\bMã:\s*(?:,\s*)?$", "", cleaned)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).rstrip()
        if cleaned.strip() in {"-", "*", "•"}:
            continue
        lines.append(cleaned)
    compact: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if blank:
                continue
            blank = True
            compact.append("")
            continue
        blank = False
        compact.append(line)
    return "\n".join(compact).strip()


def human_source_codes(evidence: list[RetrievedEvidence]) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        for value in (item.document_code, item.question_code):
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            codes.append(value.upper() if item.document_code == value else value)
    return codes


def with_human_source_footer(text: str, evidence: list[RetrievedEvidence]) -> str:
    cleaned = student_facing_answer(text)
    codes = human_source_codes(evidence)
    if not codes:
        return cleaned
    if DOCUMENT_CODE_RE.search(cleaned) or QUESTION_CODE_RE.search(cleaned):
        return cleaned
    for code in codes:
        if _token_in_text(cleaned, code):
            return cleaned
    return cleaned.rstrip() + "\n\nNguồn: " + ", ".join(codes)


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
