from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.ingestion.doc_types import infer_doc_type, normalize_doc_type
from app.ingestion.issues import IssueLog
from app.ingestion.normalize import nfc, nfc_lower, skip_sheet, normalize_question, parse_date_value

SCOPE_ANSWER = "Trong phạm vi trả lời"
SCOPE_HANDOFF = "Trong phạm vi - bot không tự trả lời & cần cán bộ hỗ trợ"
SCOPE_OOS = "Ngoài phạm vi trả lời"
SCOPE_CODE = {
    SCOPE_ANSWER: "answer_allowed",
    SCOPE_HANDOFF: "human_handoff",
    SCOPE_OOS: "out_of_scope",
}
KIND_DEADLINE = "Hạn chót"
KIND_RANGE = "Bắt đầu - kết thúc"
KIND_EVENT = "Sự kiện"
KIND_RECURRING = "Định kỳ"


def _cell(ws: Worksheet, row: int, col: int) -> str:
    return nfc(ws.cell(row, col).value)


def _row_vals(ws: Worksheet, row: int, cols: int = 12) -> list[str]:
    return [_cell(ws, row, c) for c in range(1, cols + 1)]


def _load(data: bytes):
    return load_workbook(BytesIO(data), data_only=True)


def _ds_values(wb, header: str) -> set[str]:
    if "_DS" not in wb.sheetnames:
        return set()
    ws = wb["_DS"]
    col = None
    for c in range(1, 12):
        if nfc_lower(ws.cell(2, c).value) == nfc_lower(header):
            col = c
            break
    if col is None:
        return set()
    out = set()
    for r in range(3, (ws.max_row or 3) + 1):
        v = _cell(ws, r, col)
        if v:
            out.add(v)
    return out


def _find_row(ws: Worksheet, *needles: str, max_row: int = 40) -> int | None:
    want = [nfc_lower(n) for n in needles]
    last = min(ws.max_row or 1, max_row)
    for r in range(1, last + 1):
        blob = " ".join(_row_vals(ws, r, 12)).lower()
        if all(n in blob for n in want):
            return r
    return None


def _value_after_label(ws: Worksheet, label_prefix: str, max_row: int = 20) -> str:
    prefix = nfc_lower(label_prefix)
    for r in range(1, min(ws.max_row or 1, max_row) + 1):
        if nfc_lower(_cell(ws, r, 1)).startswith(prefix) or nfc_lower(_cell(ws, r, 2)).startswith(prefix):
            for c in range(2, 6):
                v = _cell(ws, r, c)
                if v and not nfc_lower(v).startswith(prefix):
                    return v
    return ""


@dataclass
class File01:
    module_name: str = ""
    department_name: str = ""
    module_description: str = ""
    primary_audience: str = ""
    default_contact_name: str = ""
    default_contact_info: str = ""
    topics: list[dict[str, Any]] = field(default_factory=list)
    scopes_ds: set[str] = field(default_factory=set)
    audiences_ds: set[str] = field(default_factory=set)
    channels_ds: set[str] = field(default_factory=set)


@dataclass
class ParsedBundle:
    file01: File01
    faqs: list[dict[str, Any]]
    business_docs: list[dict[str, Any]]
    business_chunks: list[dict[str, Any]]
    milestones: list[dict[str, Any]]
    intro_chunks: list[dict[str, Any]]
    issues: IssueLog
    ds: dict[str, set[str]]


def parse_file01(data: bytes, issues: IssueLog) -> File01:
    wb = _load(data)
    if "1. Phạm vi trả lời" not in wb.sheetnames:
        issues.error("File 01 thiếu sheet 1. Phạm vi trả lời", "01")
        return File01()
    ws = wb["1. Phạm vi trả lời"]
    out = File01(
        module_name=_value_after_label(ws, "Tên Mô-đun"),
        department_name=_value_after_label(ws, "Phòng ban phụ trách"),
        module_description=_value_after_label(ws, "Mô tả Mô-đun"),
        primary_audience=_value_after_label(ws, "Đối tượng phục vụ chính"),
        default_contact_name=_value_after_label(ws, "Đầu mối chung"),
        default_contact_info=_value_after_label(ws, "Thông tin liên hệ chung"),
        scopes_ds=_ds_values(wb, "Phạm vi"),
        audiences_ds=_ds_values(wb, "Đối tượng"),
        channels_ds=_ds_values(wb, "Kênh"),
    )
    header = _find_row(ws, "STT", "Chủ đề")
    if header is None:
        issues.error("File 01 thiếu bảng chủ đề", "01")
        return out
    for r in range(header + 1, (ws.max_row or header) + 1):
        topic = _cell(ws, r, 3)
        if not topic:
            continue
        out.topics.append(
            {
                "stt": _cell(ws, r, 1),
                "scope": _cell(ws, r, 2),
                "topic": topic,
                "bot_behavior": _cell(ws, r, 4),
                "audience": _cell(ws, r, 5),
                "contact_name": _cell(ws, r, 6),
                "contact_info": _cell(ws, r, 7),
                "channel": _cell(ws, r, 8),
            }
        )
    return out


def parse_file02(data: bytes, issues: IssueLog) -> list[dict[str, Any]]:
    wb = _load(data)
    if "1. FAQ" not in wb.sheetnames:
        issues.error("File 02 thiếu sheet 1. FAQ", "02")
        return []
    ws = wb["1. FAQ"]
    header = _find_row(ws, "STT", "CÂU HỎI")
    if header is None:
        issues.error("File 02 thiếu header FAQ", "02")
        return []
    rows = []
    for r in range(header + 1, (ws.max_row or header) + 1):
        question = _cell(ws, r, 6)
        if not question:
            continue
        rows.append(
            {
                "stt": _cell(ws, r, 1),
                "question_code": _cell(ws, r, 2),
                "section": _cell(ws, r, 3),
                "subsection": _cell(ws, r, 4),
                "audience": _cell(ws, r, 5),
                "question": question,
                "question_norm": normalize_question(question),
                "answer": _cell(ws, r, 7),
                "legal_basis": _cell(ws, r, 8),
                "contact_name": _cell(ws, r, 9),
                "contact_info": _cell(ws, r, 10),
                "channel": _cell(ws, r, 11),
            }
        )
    return rows


def _section_starts(ws: Worksheet) -> dict[str, int]:
    found: dict[str, int] = {}
    for r in range(1, (ws.max_row or 1) + 1):
        a = nfc(_cell(ws, r, 1))
        if a.startswith("A."):
            found["A"] = r
        elif a.startswith("B."):
            found["B"] = r
        elif a.startswith("C."):
            found["C"] = r
        elif a.startswith("D."):
            found["D"] = r
        elif a.startswith("E."):
            found["E"] = r
        elif a.startswith("F."):
            found["F"] = r
    return found


def _section_end(marks: dict[str, int], letter: str, max_row: int) -> int:
    order = "ABCDEF"
    idx = order.index(letter)
    for nxt in order[idx + 1 :]:
        if nxt in marks:
            return marks[nxt]
    return max_row + 1


def _embed_text(*parts: object) -> str:
    lines: list[str] = []
    for part in parts:
        body = nfc(part)
        if body:
            lines.append(body)
    return "\n".join(lines)


def parse_file03(data: bytes, issues: IssueLog) -> tuple[list[dict], list[dict]]:
    wb = _load(data)
    docs: list[dict] = []
    chunks: list[dict] = []
    content_sheets = [n for n in wb.sheetnames if not skip_sheet(n)]
    if not content_sheets:
        issues.warning("File 03 không có sheet tài liệu", "03")
        return docs, chunks
    for name in content_sheets:
        ws = wb[name]
        title = _value_after_label(ws, "Tên nghiệp vụ", 20)
        if not title:
            continue
        raw_type = _value_after_label(ws, "Loại", 20)
        excel_type = normalize_doc_type(raw_type)
        summary = _value_after_label(ws, "Tóm tắt", 20)
        aliases = _value_after_label(ws, "Tên gọi khác", 20)
        header = {
            "sheet": name,
            "title": title,
            "summary": summary,
            "aliases": aliases,
            "audience": _value_after_label(ws, "Áp dụng cho", 20),
            "audience_excluded": _value_after_label(ws, "Không áp dụng cho", 20),
            "legal_basis": _value_after_label(ws, "Văn bản căn cứ", 20),
            "contact": _value_after_label(ws, "Đầu mối hỗ trợ", 20),
            "effective_from": _value_after_label(ws, "Hiệu lực từ", 20),
            "effective_to": _value_after_label(ws, "Hiệu lực đến", 20),
            "doc_type_excel": excel_type[0] if excel_type else (raw_type or ""),
        }
        marks = _section_starts(ws)
        last = (ws.max_row or 1) + 1
        sheet_chunks: list[dict[str, Any]] = []

        def add_chunk(kind: str, text: str, extra: dict | None = None) -> None:
            body = nfc(text)
            if not body:
                return
            payload = {
                "sheet": name,
                "title": title,
                "kind": kind,
                "text": body,
                "effective_from": header["effective_from"],
                "effective_to": header["effective_to"],
            }
            if extra:
                payload.update(extra)
            sheet_chunks.append(payload)

        if summary:
            add_chunk("doc_summary", _embed_text(title, summary, aliases))

        b0 = marks.get("B")
        if b0:
            for r in range(b0 + 2, _section_end(marks, "B", last - 1)):
                content = _cell(ws, r, 4)
                if not content:
                    continue
                section, sub = _cell(ws, r, 2), _cell(ws, r, 3)
                situation, handling = _cell(ws, r, 5), _cell(ws, r, 6)
                add_chunk(
                    "regulation",
                    _embed_text(title, section, sub, content, situation, handling),
                    {"section": section, "subsection": sub, "situation": situation, "handling": handling},
                )
        c0 = marks.get("C")
        if c0:
            for r in range(c0 + 2, _section_end(marks, "C", last - 1)):
                sit = _cell(ws, r, 2)
                if not sit:
                    continue
                handling = _cell(ws, r, 3)
                cond_kind = _cell(ws, r, 6) or _cell(ws, r, 4)
                add_chunk(
                    "condition",
                    _embed_text(title, sit, handling, cond_kind),
                    {"handling": handling, "condition_kind": cond_kind},
                )
        d0 = marks.get("D")
        if d0:
            meta_bits = []
            for r in range(d0 + 1, _section_end(marks, "D", last - 1)):
                lab, val = _cell(ws, r, 1), _cell(ws, r, 2) or _cell(ws, r, 3)
                if lab and val and not lab.startswith("D."):
                    meta_bits.append(f"{lab}: {val}")
            if meta_bits:
                add_chunk("procedure_meta", _embed_text(title, *meta_bits))
        e0 = marks.get("E")
        if e0:
            for r in range(e0 + 2, _section_end(marks, "E", last - 1)):
                item = _cell(ws, r, 2)
                if not item:
                    continue
                form, spec, required = _cell(ws, r, 3), _cell(ws, r, 5), _cell(ws, r, 6)
                add_chunk(
                    "dossier",
                    _embed_text(title, "Hồ sơ", item, form, spec, required),
                    {"required": required, "form": form, "spec": spec},
                )
        f0 = marks.get("F")
        if f0:
            for r in range(f0 + 2, last):
                step = _cell(ws, r, 2)
                if not step:
                    continue
                link, unit, duration, channel = _cell(ws, r, 3), _cell(ws, r, 4), _cell(ws, r, 5), _cell(ws, r, 6)
                add_chunk(
                    "step",
                    _embed_text(title, step, link, unit, duration, channel),
                    {"channel": channel, "link": link, "unit": unit, "duration": duration},
                )

        kinds = {c["kind"] for c in sheet_chunks if c["kind"] != "doc_summary"}
        doc_type, doc_type_code = infer_doc_type(kinds)
        for item in sheet_chunks:
            item["doc_type"] = doc_type
            item["doc_type_code"] = doc_type_code
        header["doc_type"] = doc_type
        header["doc_type_code"] = doc_type_code
        docs.append(header)
        chunks.extend(sheet_chunks)
        if not summary:
            issues.warning(f"File 03 sheet {name}: thiếu tóm tắt", "03")
        table_chunks = [c for c in sheet_chunks if c["kind"] != "doc_summary"]
        if not table_chunks:
            issues.warning(f"File 03 sheet {name}: không có dòng B–F", "03")
    if not docs:
        issues.warning("File 03 không có tài liệu đủ title", "03")
    return docs, chunks


def _cell_date(ws: Worksheet, row: int, col: int) -> str:
    return parse_date_value(ws.cell(row, col).value)


def parse_file04(data: bytes, issues: IssueLog) -> list[dict[str, Any]]:
    wb = _load(data)
    if "1. Mốc thời gian" not in wb.sheetnames:
        issues.error("File 04 thiếu sheet 1. Mốc thời gian", "04")
        return []
    ws = wb["1. Mốc thời gian"]
    header = _find_row(ws, "STT", "TÊN MỐC")
    if header is None:
        issues.error("File 04 thiếu header mốc", "04")
        return []
    rows = []
    for r in range(header + 1, (ws.max_row or header) + 1):
        name = _cell(ws, r, 4)
        if not name:
            continue
        start = _cell_date(ws, r, 6)
        end = _cell_date(ws, r, 7)
        rows.append(
            {
                "stt": _cell(ws, r, 1),
                "milestone_id": _cell(ws, r, 2),
                "group": _cell(ws, r, 3),
                "name": name,
                "kind": _cell(ws, r, 5),
                "start": start,
                "end": end,
                "audience": _cell(ws, r, 8),
                "academic_term": _cell(ws, r, 9),
                "full_text": _cell(ws, r, 10),
                "legal_basis": _cell(ws, r, 11),
                "note": _cell(ws, r, 12),
            }
        )
    return rows


def parse_file05(data: bytes, issues: IssueLog) -> list[dict[str, Any]]:
    wb = _load(data)
    chunks: list[dict[str, Any]] = []
    sheets = [n for n in wb.sheetnames if not skip_sheet(n)]
    if not sheets:
        issues.warning("File 05 không có sheet bài", "05")
        return chunks
    for name in sheets:
        ws = wb[name]
        title = _value_after_label(ws, "Tên bài", 12)
        if not title:
            continue
        summary = _value_after_label(ws, "Tóm tắt", 12)
        aliases = _value_after_label(ws, "Tên gọi khác", 12)
        if not summary:
            issues.error(f"File 05 sheet {name}: thiếu tóm tắt", "05")
            continue
        chunks.append(
            {
                "sheet": name,
                "title": title,
                "kind": "intro_summary",
                "text": f"{title}\n{summary}\n{aliases}",
                "audience": _value_after_label(ws, "Đối tượng áp dụng", 12),
                "source_url": _value_after_label(ws, "Nguồn", 12),
            }
        )
        header = _find_row(ws, "STT", "Tiêu đề mục", max_row=20)
        if header is None:
            continue
        for r in range(header + 1, (ws.max_row or header) + 1):
            heading, body = _cell(ws, r, 2), _cell(ws, r, 3)
            if not body:
                continue
            chunks.append(
                {
                    "sheet": name,
                    "title": title,
                    "kind": "intro_section",
                    "heading": heading,
                    "text": _embed_text(title, heading, body),
                }
            )
    return chunks


def parse_bundle(files: dict[int, bytes]) -> ParsedBundle:
    issues = IssueLog()
    f01 = parse_file01(files[1], issues)
    faqs = parse_file02(files[2], issues)
    docs, biz = parse_file03(files[3], issues)
    milestones = parse_file04(files[4], issues)
    intros = parse_file05(files[5], issues)
    wb1 = _load(files[1])
    ds = {
        "scope": _ds_values(wb1, "Phạm vi"),
        "audience": _ds_values(wb1, "Đối tượng"),
        "doc_type": _ds_values(wb1, "Loại tài liệu"),
        "kind": _ds_values(wb1, "Loại mốc"),
        "channel": _ds_values(wb1, "Kênh"),
        "fee": _ds_values(wb1, "Lệ phí"),
        "deadline": _ds_values(wb1, "Thời hạn xử lý"),
        "condition": _ds_values(wb1, "Loại điều kiện"),
    }
    return ParsedBundle(f01, faqs, docs, biz, milestones, intros, issues, ds)
