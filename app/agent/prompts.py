from __future__ import annotations

from app.agent.models import RetrievedEvidence, TrainingSystem

SYSTEM_GENERATE = """Bạn là trợ lý quy định khảo thí của Trường Đại học Kinh tế - Luật (UEL).
Chỉ dùng ngữ cảnh STAIR/FAQ được cung cấp. Không dùng kiến thức ngoài để kết luận quy định UEL.
Không nêu email, hotline, mật khẩu, API key hay dữ liệu cá nhân.
Không nêu số tiền lệ phí nếu nguồn ghi chưa xác định.
Trả lời tiếng Việt, ngắn, trung lập.
Mọi kết luận phải kèm mã nguồn có trong ngữ cảnh (TLxx hoặc mã câu hỏi dạng I.1.001).
Nếu ngữ cảnh không đủ, nói rõ là không đủ dữ liệu — không suy đoán."""

ROUTING_SYSTEM = """Phân loại câu hỏi người học UEL vào đúng một scope_type.
answer_allowed: quy định khảo thí chung (hình thức thi, phúc khảo, điểm I, SEB hướng dẫn).
human_required: hồ sơ/kết quả/điểm/khiếu nại cá nhân, cấm thi, không có tên trong danh sách.
out_of_scope: học phí, TKB, đăng ký học phần, cài phần mềm, LMS, học bổng, phòng ban khác.
Chỉ trả JSON theo schema."""

METADATA_SYSTEM = """Rút metadata từ câu hỏi khảo thí.
training_system: dhcq | sdh | vb2_vlvh | unknown (không đoán nếu không nêu).
topic: phuc_khao | diem_i_nhan | diem_i_tra | seb | hinh_thuc_thi | fee | other.
is_fee_question: true nếu hỏi mức thu/số tiền/lệ phí.
Không bịa mã tài liệu hay mã câu hỏi."""

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


def generate_user_prompt(
    query: str,
    evidence: list[RetrievedEvidence],
    training_system: TrainingSystem,
) -> str:
    blocks = [
        f"Câu hỏi: {query}",
        f"Hệ đào tạo (nếu có): {training_system}",
        "Ngữ cảnh đã duyệt:",
    ]
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


def extractive_fallback(evidence: list[RetrievedEvidence]) -> str:
    lines = [
        "Mô hình đang quá tải nên tôi trích đúng đoạn đã duyệt (chưa tóm tắt bằng LLM).",
        "",
    ]
    for item in evidence[:3]:
        label = item.document_code or item.question_code or "nguồn"
        excerpt = readable_stair_excerpt(item.stair_markdown)
        if not excerpt:
            continue
        lines.append(f"[{label}] {excerpt}")
        lines.append("")
    return "\n".join(lines).strip()
