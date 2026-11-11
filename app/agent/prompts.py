from __future__ import annotations

from app.agent.models import RetrievedEvidence, TrainingSystem

# Legacy generate fallback (tests with legacy_mode). Production uses module_generate_system
# plus prompt_pack from departments.yaml /admin.
SYSTEM_GENERATE = (
    "Chỉ dùng ngữ cảnh được cung cấp. Không nêu secret hay dữ liệu cá nhân. "
    "Trả lời tiếng Việt, ngắn, dễ hiểu. Không in mã gold: hay chunk_id. "
    "Không suy đoán khi ngữ cảnh thiếu."
)

# Used only when AgentDeps.legacy_mode is True. Production routing is Template 1.
ROUTING_SYSTEM = """Select exactly one scope_type for this module.
answer_allowed: the module may answer from approved evidence.
human_required: a specific person's case, file, or result.
out_of_scope: another unit's work.
Return JSON only."""

# Default metadata prompt when profile=assessment and prompt_pack.metadata_system is empty.
METADATA_SYSTEM = """Extract metadata from the question.
training_system: dhcq | sdh | vb2_vlvh | unknown (do not guess).
topic: phuc_khao | diem_i_nhan | diem_i_tra | seb | hinh_thuc_thi | fee | other.
is_fee_question: true if asking a fee amount.
Do not invent document or question codes."""

ROUTING_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "scope_type": {
            "type": "string",
            "enum": ["answer_allowed", "human_required", "out_of_scope"],
        }
    },
    "required": ["scope_type"],
}

METADATA_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "training_system": {
            "type": "string",
            "enum": ["dhcq", "sdh", "vb2_vlvh", "unknown"],
        },
        "topic": {
            "type": "string",
            "enum": [
                "phuc_khao",
                "diem_i_nhan",
                "diem_i_tra",
                "seb",
                "hinh_thuc_thi",
                "fee",
                "other",
            ],
        },
        "is_fee_question": {"type": "boolean"},
    },
    "required": ["training_system", "topic", "is_fee_question"],
}


_TRAINING_CODES = ("dhcq", "sdh", "vb2_vlvh")


def _training_labels(glossary: dict[str, str] | None) -> dict[str, str]:
    labels: dict[str, str] = {}
    for key, value in (glossary or {}).items():
        folded = key.strip().casefold()
        display = f"{key.strip()} ({value.strip()})" if value.strip() else key.strip()
        if folded in {"đhcq", "dhcq"}:
            labels["dhcq"] = display
        elif folded in {"sđh", "sdh"}:
            labels["sdh"] = display
        elif folded in {"vb2/vlvh", "vb2", "vlvh"}:
            labels["vb2_vlvh"] = display
    return labels


def generate_user_prompt(
    query: str,
    evidence: list[RetrievedEvidence],
    training_system: TrainingSystem,
    training_systems: list[str] | None = None,
    *,
    writing_notes: str = "",
    glossary: dict[str, str] | None = None,
) -> str:
    labels = _training_labels(glossary)
    systems = [item for item in (training_systems or []) if item in _TRAINING_CODES]
    if not systems and training_system in _TRAINING_CODES:
        systems = [training_system]
    blocks = [f"Câu hỏi: {query}"]
    if systems:
        named = [labels.get(item, item) for item in systems]
        blocks.append("Hệ đào tạo được hỏi: " + ", ".join(named))
    blocks.append("Ngữ cảnh đã duyệt:")
    for index, item in enumerate(evidence, start=1):
        codes = [item.chunk_id]
        if item.document_code:
            codes.append(item.document_code)
        if item.question_code:
            codes.append(item.question_code)
        markdown = item.stair_markdown
        if len(markdown) > 1200:
            markdown = markdown[:1200] + "\n…"
        blocks.append(f"[{index}] Mã: {', '.join(codes)}\n{markdown}")
    notes = writing_notes.strip()
    if notes:
        blocks.append(notes)
    return "\n\n".join(blocks)


_STAIR_META_PREFIXES = (
    "- Phòng ban:",
    "- Mô-đun:",
    "- Đối tượng:",
    "- Trạng thái release:",
    "- Mã tài liệu:",
    "- Mã câu hỏi:",
    "- Hiệu lực:",
    "- Phân mục:",
    "- Phân mục chi tiết:",
    "- Có văn bản căn cứ:",
    "- Chủ đề tài liệu:",
)

_STAIR_SKIP = frozenset(
    {
        "chưa có văn bản căn cứ trong nguồn.",
        "không có điều kiện/ngoại lệ gắn với mục này trong nguồn.",
        "## văn bản căn cứ",
    }
)


def readable_stair_excerpt(markdown: str, *, max_chars: int = 900) -> str:
    title = ""
    kept: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            continue
        if any(stripped.startswith(prefix) for prefix in _STAIR_META_PREFIXES):
            continue
        if stripped.lower().startswith("nguồn:") and ".xlsx" in stripped.lower():
            continue
        if stripped.casefold() in _STAIR_SKIP:
            continue
        if stripped in {"##", "#", "…", "..."}:
            continue
        kept.append(stripped if stripped else "")
    compact: list[str] = []
    blank = False
    for line in kept:
        if not line:
            if blank:
                continue
            blank = True
            compact.append("")
            continue
        blank = False
        compact.append(line)
    body = "\n".join(compact).strip()
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "…"
    if title and body:
        return f"{title}\n{body}"
    return title or body


def fallback_evidence(evidence: list[RetrievedEvidence]) -> list[RetrievedEvidence]:
    return [item for item in evidence[:3] if readable_stair_excerpt(item.stair_markdown)]


def extractive_fallback(evidence: list[RetrievedEvidence]) -> str:
    lines = [
        "Mình trích đúng dữ liệu đã duyệt (chưa tóm tắt):",
        "",
    ]
    for item in fallback_evidence(evidence):
        label = item.document_code or item.question_code or "nguồn"
        excerpt = readable_stair_excerpt(item.stair_markdown)
        if not excerpt:
            continue
        lines.append(f"[{label}] {excerpt}")
        lines.append("")
    return "\n".join(lines).strip()
