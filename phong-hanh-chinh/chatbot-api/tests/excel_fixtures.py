from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

TEMPLATES = Path(__file__).resolve().parents[2] / "chatbot-data" / "templates"

SCOPE_ANSWER = "Trong phạm vi trả lời"
SCOPE_HANDOFF = "Trong phạm vi - bot không tự trả lời & cần cán bộ hỗ trợ"
AUDIENCE = "Tất cả người học"


def template_slot(n: int) -> Path:
    for path in TEMPLATES.iterdir():
        if path.suffix.lower() == ".xlsx" and path.name.startswith(str(n)):
            return path
    raise FileNotFoundError(f"template {n}")


def _set_label(ws, label_prefix: str, value: str, col: int = 3) -> None:
    prefix = label_prefix.lower()
    for r in range(1, 16):
        a = str(ws.cell(r, 1).value or "")
        if a.lower().startswith(prefix):
            ws.cell(r, col).value = value
            return


def fill_file01(
    *,
    module_name: str = "Thông tin chung",
    topic: str = "Hạn phúc khảo",
    scope: str = SCOPE_ANSWER,
    extra_topics: list[tuple[str, str]] | None = None,
    channel: str = "",
    primary_audience: str = AUDIENCE,
    audience: str = AUDIENCE,
) -> bytes:
    wb = load_workbook(template_slot(1))
    ws = wb["1. Phạm vi trả lời"]
    _set_label(ws, "Tên Mô-đun", module_name)
    _set_label(ws, "Phòng ban phụ trách", "Phòng Bảo đảm chất lượng")
    _set_label(ws, "Mô tả Mô-đun", "Hỗ trợ quy định khảo thí.")
    _set_label(ws, "Đối tượng phục vụ chính", primary_audience)
    ws.cell(13, 1).value = 1
    ws.cell(13, 2).value = scope
    ws.cell(13, 3).value = topic
    ws.cell(13, 4).value = "Trả lời theo FAQ và tài liệu."
    ws.cell(13, 5).value = audience
    if channel:
        ws.cell(13, 8).value = channel
    if extra_topics:
        for i, (tp, sc) in enumerate(extra_topics, start=14):
            ws.cell(i, 1).value = i - 12
            ws.cell(i, 2).value = sc
            ws.cell(i, 3).value = tp
            ws.cell(i, 4).value = "Xử lý theo quy định."
            ws.cell(i, 5).value = audience
            ws.cell(i, 6).value = "P.BDCL"
            ws.cell(i, 7).value = "phongbdcl@uel.edu.vn"
    from io import BytesIO

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def fill_file02(*, duplicate_question: bool = False, code_dup: bool = False) -> bytes:
    wb = load_workbook(template_slot(2))
    ws = wb["1. FAQ"]
    ws.cell(3, 1).value = 1
    ws.cell(3, 2).value = "I.001"
    ws.cell(3, 3).value = "Phúc khảo"
    ws.cell(3, 5).value = AUDIENCE
    ws.cell(3, 6).value = "Hạn phúc khảo ĐHCQ là bao lâu?"
    ws.cell(3, 7).value = "02 ngày làm việc kể từ ngày công bố điểm."
    if duplicate_question:
        ws.cell(4, 1).value = 2
        ws.cell(4, 2).value = "I.002"
        ws.cell(4, 3).value = "Phúc khảo"
        ws.cell(4, 5).value = AUDIENCE
        ws.cell(4, 6).value = "Hạn phúc khảo ĐHCQ là bao lâu?"
        ws.cell(4, 7).value = "Câu khác."
    if code_dup:
        ws.cell(4, 1).value = 2
        ws.cell(4, 2).value = "I.001"
        ws.cell(4, 3).value = "Phúc khảo"
        ws.cell(4, 5).value = AUDIENCE
        ws.cell(4, 6).value = "Câu khác hoàn toàn?"
        ws.cell(4, 7).value = "Trả lời."
    from io import BytesIO

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def fill_file03(*, doc_type: str = "Quy định", procedure: bool = False) -> bytes:
    wb = load_workbook(template_slot(3))
    ws = wb["Tài liệu 1"]
    for rng in list(ws.merged_cells.ranges):
        ws.unmerge_cells(str(rng))
    _set_label(ws, "Tên nghiệp vụ", "Quy định phúc khảo")
    _set_label(ws, "Loại", doc_type)
    _set_label(ws, "Tóm tắt", "Hướng dẫn thời hạn và điều kiện phúc khảo điểm thi.")
    ws.cell(16, 1).value = 1
    ws.cell(16, 2).value = "Thời hạn"
    ws.cell(16, 4).value = "ĐHCQ nộp phúc khảo trong 02 ngày làm việc."
    if procedure:
        ws.cell(31, 2).value = "Kết quả phúc khảo trên Portal"
        ws.cell(43, 2).value = "Đơn đăng ký phúc khảo"
        ws.cell(43, 6).value = "Có"
        ws.cell(50, 2).value = "Đăng nhập Portal UEL"
        ws.cell(50, 6).value = "Trực tuyến"
    from io import BytesIO

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def empty_file04() -> bytes:
    return template_slot(4).read_bytes()


def fill_file04(rows: list[dict] | None = None) -> bytes:
    wb = load_workbook(template_slot(4))
    ws = wb["1. Mốc thời gian"]
    for i, row in enumerate(rows or [], start=3):
        ws.cell(i, 1).value = i - 2
        ws.cell(i, 2).value = row.get("milestone_id") or f"M{i - 2:03d}"
        ws.cell(i, 3).value = row.get("group") or "Nhóm"
        ws.cell(i, 4).value = row.get("name") or "Mốc"
        ws.cell(i, 5).value = row.get("kind") or "Hạn chót"
        ws.cell(i, 6).value = row.get("start") or None
        ws.cell(i, 7).value = row.get("end") or None
        ws.cell(i, 8).value = row.get("audience") or AUDIENCE
        ws.cell(i, 9).value = row.get("academic_term") or "2026-2027"
        ws.cell(i, 10).value = row.get("full_text") or "Nội dung mốc."
        ws.cell(i, 12).value = row.get("note") or ""
    from io import BytesIO

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def empty_file05() -> bytes:
    return template_slot(5).read_bytes()


def valid_pack(**file01_kw) -> dict[int, bytes]:
    return {
        1: fill_file01(**file01_kw),
        2: fill_file02(),
        3: fill_file03(),
        4: empty_file04(),
        5: empty_file05(),
    }
