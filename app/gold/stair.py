from __future__ import annotations

from datetime import date

from app.ingestion.enums import CANONICAL_DEPARTMENT_NAME, CANONICAL_MODULE_NAME
from app.ingestion.normalize import normalize_rich_text, normalize_space


def stair_header(
    *,
    title: str,
    document_code: str | None,
    audience: str = "Người học",
    release_status: str,
    extra_lines: list[str] | None = None,
) -> str:
    lines = [
        f"# {title.strip()}",
        "",
        f"- Phòng ban: {CANONICAL_DEPARTMENT_NAME}",
        f"- Mô-đun: {CANONICAL_MODULE_NAME}",
        f"- Đối tượng: {audience}",
        f"- Trạng thái release: {release_status}",
    ]
    if document_code:
        lines.insert(5, f"- Mã tài liệu: {document_code}")
    if extra_lines:
        lines.extend(extra_lines)
    lines.append("")
    return "\n".join(lines)


def source_footer(source_file: str, source_sheet: str, source_row: int) -> str:
    return f"Nguồn: {source_file} / {source_sheet} / dòng {source_row}"


def serialize_faq(
    *,
    question: str,
    question_code: str,
    answer: str,
    legal_basis: str | None,
    category: str | None,
    subcategory: str | None,
    release_status: str,
    source_file: str,
    source_sheet: str,
    source_row: int,
) -> str:
    extra = [f"- Mã câu hỏi: {question_code}"]
    if category:
        extra.append(f"- Phân mục: {category}")
    if subcategory:
        extra.append(f"- Phân mục chi tiết: {subcategory}")
    extra.append(f"- Có văn bản căn cứ: {'có' if legal_basis else 'không'}")
    body = [
        stair_header(
            title=question, document_code=None, release_status=release_status, extra_lines=extra
        ),
        "## Câu trả lời",
        "",
        normalize_rich_text(answer),
        "",
        "## Văn bản căn cứ",
        "",
        normalize_rich_text(legal_basis) if legal_basis else "Chưa có văn bản căn cứ trong nguồn.",
        "",
        source_footer(source_file, source_sheet, source_row),
        "",
    ]
    return "\n".join(body)


def serialize_regulation(
    *,
    document_title: str,
    document_code: str,
    heading: str | None,
    subheading: str | None,
    content: str | None,
    inline_condition: str | None,
    resolution: str | None,
    related_conditions: list[tuple[str | None, str | None, str | None]],
    release_status: str,
    source_file: str,
    source_sheet: str,
    source_row: int,
) -> str:
    section_title = heading or document_title
    extra = [f"- Chủ đề tài liệu: {document_title}"]
    parts = [
        stair_header(
            title=section_title,
            document_code=document_code,
            release_status=release_status,
            extra_lines=extra,
        ),
        f"## {section_title}",
        "",
    ]
    if subheading:
        parts.extend([normalize_rich_text(subheading), ""])
    if content:
        parts.extend([normalize_rich_text(content), ""])
    if resolution:
        parts.extend(["### Kết luận/xử lý", "", normalize_rich_text(resolution), ""])
    if inline_condition:
        parts.extend(["### Điều kiện trên cùng mục", "", normalize_rich_text(inline_condition), ""])
    parts.extend(_conditions_block(related_conditions))
    parts.extend([source_footer(source_file, source_sheet, source_row), ""])
    return "\n".join(parts)


def serialize_condition(
    *,
    document_title: str,
    document_code: str,
    condition_type: str,
    scenario: str | None,
    resolution: str | None,
    release_status: str,
    source_file: str,
    source_sheet: str,
    source_row: int,
) -> str:
    title = scenario or f"{document_title} — điều kiện/ngoại lệ"
    extra = [
        f"- Chủ đề tài liệu: {document_title}",
        f"- Loại: {condition_type}",
    ]
    parts = [
        stair_header(
            title=title,
            document_code=document_code,
            release_status=release_status,
            extra_lines=extra,
        ),
        "## Tình huống",
        "",
        normalize_rich_text(scenario or document_title),
        "",
    ]
    if resolution:
        parts.extend(["## Cách xử lý", "", normalize_rich_text(resolution), ""])
    parts.extend([source_footer(source_file, source_sheet, source_row), ""])
    return "\n".join(parts)


def serialize_procedure(
    *,
    document_title: str,
    document_code: str,
    summary: str | None,
    result: str | None,
    processing_time_type: str | None,
    max_working_days: int | None,
    location: str | None,
    submission_url: str | None,
    special_schedule: str | None,
    fee_type: str | None,
    fee_amount_vnd: int | None,
    fee_note: str | None,
    answer_policy: str | None,
    related_conditions: list[tuple[str | None, str | None, str | None]],
    release_status: str,
    effective_from: date | None,
    effective_to: date | None,
    source_file: str,
    source_sheet: str,
    source_row: int,
) -> str:
    extra = [_effective_line(effective_from, effective_to)]
    parts = [
        stair_header(
            title=document_title,
            document_code=document_code,
            release_status=release_status,
            extra_lines=extra,
        ),
    ]
    if summary:
        parts.extend(["## Tóm tắt", "", normalize_rich_text(summary), ""])
    if result:
        parts.extend(["## Kết quả", "", normalize_rich_text(result), ""])
    parts.extend(
        [
            "## Thời hạn xử lý",
            "",
            _processing_time_text(processing_time_type, max_working_days, special_schedule),
            "",
            "## Nơi nộp / kênh",
            "",
            _join_present(location, submission_url) or "Không nêu trong nguồn.",
            "",
            "## Lệ phí",
            "",
            _fee_text(fee_type, fee_amount_vnd, fee_note, answer_policy),
            "",
        ]
    )
    parts.extend(_conditions_block(related_conditions))
    parts.extend([source_footer(source_file, source_sheet, source_row), ""])
    return "\n".join(parts)


def serialize_dossier(
    *,
    document_title: str,
    document_code: str,
    items: list[tuple[str, str | None, str | None, bool | None]],
    release_status: str,
    source_file: str,
    source_sheet: str,
    source_row: int,
) -> str:
    extra = [f"- Chủ đề tài liệu: {document_title}"]
    lines = [
        stair_header(
            title=f"{document_title} — Hồ sơ",
            document_code=document_code,
            release_status=release_status,
            extra_lines=extra,
        ),
        "## Thành phần hồ sơ",
        "",
    ]
    for name, form_url, quantity, required in items:
        flag = (
            "bắt buộc"
            if required
            else "không bắt buộc"
            if required is False
            else "không nêu bắt buộc"
        )
        detail = f"- {name} ({flag})"
        if quantity:
            detail += f"; số lượng: {quantity}"
        if form_url:
            detail += f"; biểu mẫu: {form_url}"
        lines.append(detail)
    if not items:
        lines.append("Không có thành phần hồ sơ trong nguồn.")
    lines.extend(["", source_footer(source_file, source_sheet, source_row), ""])
    return "\n".join(lines)


def serialize_step(
    *,
    document_title: str,
    document_code: str,
    step_number: int,
    instruction: str,
    time_requirement: str | None,
    url_or_location: str | None,
    responsible_unit: str | None,
    channel: str | None,
    release_status: str,
    source_file: str,
    source_sheet: str,
    source_row: int,
) -> str:
    extra = [f"- Chủ đề tài liệu: {document_title}", f"- Bước: {step_number}"]
    parts = [
        stair_header(
            title=f"{document_title} — Bước {step_number}",
            document_code=document_code,
            release_status=release_status,
            extra_lines=extra,
        ),
        "## Hướng dẫn",
        "",
        normalize_rich_text(instruction),
        "",
        "## Thời hạn của bước",
        "",
        normalize_rich_text(time_requirement)
        if time_requirement
        else "Không nêu thời hạn riêng cho bước này.",
        "",
    ]
    extras = _join_present(url_or_location, responsible_unit, channel)
    if extras:
        parts.extend(["## Địa điểm / đơn vị / kênh", "", extras, ""])
    parts.extend([source_footer(source_file, source_sheet, source_row), ""])
    return "\n".join(parts)


def headings_related(heading: str | None, scenario: str | None) -> bool:
    left = normalize_space(heading or "").casefold()
    right = normalize_space(scenario or "").casefold()
    if not left or not right:
        return False
    return left in right or right in left


def _conditions_block(related: list[tuple[str | None, str | None, str | None]]) -> list[str]:
    parts = ["## Điều kiện và ngoại lệ", ""]
    if not related:
        parts.extend(["Không có điều kiện/ngoại lệ gắn với mục này trong nguồn.", ""])
        return parts
    for condition_type, scenario, resolution in related:
        label = condition_type or "note"
        parts.append(f"### {label}")
        if scenario:
            parts.extend(["", normalize_rich_text(scenario)])
        if resolution:
            parts.extend(["", normalize_rich_text(resolution)])
        parts.append("")
    return parts


def _processing_time_text(
    processing_time_type: str | None,
    max_working_days: int | None,
    special_schedule: str | None,
) -> str:
    if processing_time_type == "working_days" and max_working_days is not None:
        text = f"{max_working_days} ngày làm việc"
    elif processing_time_type == "same_day":
        text = "Trong ngày"
    elif processing_time_type == "case_by_case":
        text = "Tùy trường hợp"
    else:
        text = "Không nêu thời hạn tổng trong nguồn."
    if special_schedule:
        text = f"{text}. {normalize_rich_text(special_schedule)}"
    return text


def _fee_text(
    fee_type: str | None,
    fee_amount_vnd: int | None,
    fee_note: str | None,
    answer_policy: str | None,
) -> str:
    if fee_type == "unknown" or answer_policy in {"insufficient_evidence", "human_handoff"}:
        note = normalize_rich_text(fee_note) if fee_note else "Chưa xác định."
        return f"{note} Không nêu số tiền khi nguồn chưa xác định mức phí."
    if fee_amount_vnd is not None:
        text = f"{fee_amount_vnd} VND"
        if fee_note:
            text = f"{text}. {normalize_rich_text(fee_note)}"
        return text
    if fee_note:
        return normalize_rich_text(fee_note)
    return "Không nêu lệ phí trong nguồn."


def _effective_line(effective_from: date | None, effective_to: date | None) -> str:
    start = effective_from.isoformat() if effective_from else "không nêu"
    end = effective_to.isoformat() if effective_to else "không nêu"
    return f"- Hiệu lực: từ {start} đến {end}"


def _join_present(*parts: str | None) -> str | None:
    values = [normalize_rich_text(part) for part in parts if part]
    return "\n".join(values) if values else None
