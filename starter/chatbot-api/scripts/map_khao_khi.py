"""Map data/P.BDCL (layout cũ) sang 5 file template 3.0. Không sửa template/ gốc."""

from __future__ import annotations

import shutil
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "P.BDCL"
TEMPLATES = ROOT / "starter" / "chatbot-data" / "templates"
DEST = ROOT / "starter" / "chatbot-data" / "modules" / "khao_khi" / "seed"
DBCL_DEST = ROOT / "phong-bao-dam-chat-luong" / "chatbot-data" / "modules" / "khao_khi" / "seed"

AUDIENCE = "Tất cả người học"
MODULE_NAME = "Mô-đun Khảo thí"


def _slot(n: int) -> Path:
    for path in TEMPLATES.iterdir():
        if path.suffix.lower() == ".xlsx" and path.name.startswith(str(n)):
            return path
    raise FileNotFoundError(n)


def _set(ws, prefix: str, value: str, col: int = 3) -> None:
    p = prefix.lower()
    for r in range(1, 20):
        a = str(ws.cell(r, 1).value or "")
        if a.lower().startswith(p):
            ws.cell(r, col).value = value
            return


def _cell(ws, r, c) -> str:
    v = ws.cell(r, c).value
    return "" if v is None else str(v).strip()


def map_file01() -> None:
    src = next(SRC.glob("1*.xlsx"))
    src_wb = load_workbook(src, data_only=True)
    src_ws = src_wb["1. Phạm vi trả lời"]
    wb = load_workbook(_slot(1))
    ws = wb["1. Phạm vi trả lời"]
    _set(ws, "Tên Mô-đun", MODULE_NAME)
    _set(ws, "Phòng ban phụ trách", "Phòng Bảo đảm chất lượng")
    _set(ws, "Mô tả Mô-đun", "Hỗ trợ quy định thi, phúc khảo, điểm I và hình thức thi tại UEL.")
    _set(ws, "Đối tượng phục vụ chính", AUDIENCE)
    _set(ws, "Đầu mối chung", "Phòng Bảo đảm chất lượng")
    _set(ws, "Thông tin liên hệ chung", "phongbdcl@uel.edu.vn")
    dest_row = 13
    for r in range(10, (src_ws.max_row or 10) + 1):
        topic = _cell(src_ws, r, 3).lstrip("- ").strip()
        scope = _cell(src_ws, r, 2)
        if not topic or not scope:
            continue
        ws.cell(dest_row, 1).value = dest_row - 12
        ws.cell(dest_row, 2).value = scope
        ws.cell(dest_row, 3).value = topic
        ws.cell(dest_row, 4).value = _cell(src_ws, r, 4) or "Xử lý theo quy định khảo thí."
        ws.cell(dest_row, 5).value = AUDIENCE
        ws.cell(dest_row, 6).value = _cell(src_ws, r, 5)
        ws.cell(dest_row, 7).value = _cell(src_ws, r, 6)
        ws.cell(dest_row, 8).value = _cell(src_ws, r, 7)
        dest_row += 1
    wb.save(DEST / "1. Thong tin Mo-dun - Khao khi.xlsx")


def map_file02() -> None:
    src = next(SRC.glob("2*.xlsx"))
    src_wb = load_workbook(src, data_only=True)
    src_ws = src_wb["1. FAQ"]
    wb = load_workbook(_slot(2))
    ws = wb["1. FAQ"]
    dest = 3
    for r in range(5, (src_ws.max_row or 5) + 1):
        question = _cell(src_ws, r, 6)
        if not question:
            continue
        ws.cell(dest, 1).value = dest - 2
        ws.cell(dest, 2).value = _cell(src_ws, r, 3) or f"I.{dest - 2:03d}"
        ws.cell(dest, 3).value = _cell(src_ws, r, 4) or "Khảo thí"
        ws.cell(dest, 4).value = _cell(src_ws, r, 5)
        ws.cell(dest, 5).value = AUDIENCE
        ws.cell(dest, 6).value = question
        ws.cell(dest, 7).value = _cell(src_ws, r, 7)
        ws.cell(dest, 8).value = _cell(src_ws, r, 8)
        dest += 1
    wb.save(DEST / "2. FAQ - Khao khi.xlsx")


def map_file03() -> None:
    src = next(SRC.glob("3*.xlsx"))
    src_wb = load_workbook(src, data_only=True)
    wb = load_workbook(_slot(3))
    template_sheet = wb["Tài liệu 1"]
    first = True
    idx = 1
    for name in src_wb.sheetnames:
        if name.lower() in {"hướng dẫn", "_ds", "mẫu"}:
            continue
        src_ws = src_wb[name]
        title = ""
        summary = ""
        aliases = ""
        for r in range(1, 12):
            lab = _cell(src_ws, r, 2).lower()
            val = _cell(src_ws, r, 3)
            if "tên chủ đề" in lab or "tên nghiệp vụ" in lab:
                title = val
            elif "tóm tắt" in lab:
                summary = val
            elif "từ khóa" in lab:
                aliases = val
        if not title:
            continue
        if first:
            ws = template_sheet
            first = False
        else:
            ws = wb.copy_worksheet(template_sheet)
            ws.title = f"Tài liệu {idx}"
        for rng in list(ws.merged_cells.ranges):
            ws.unmerge_cells(str(rng))
        _set(ws, "Tên nghiệp vụ", title)
        _set(ws, "Loại", "Quy định")
        _set(ws, "Tóm tắt", summary or title)
        _set(ws, "Tên gọi khác", aliases)
        out_r = 16
        in_b = False
        for r in range(1, (src_ws.max_row or 1) + 1):
            a = _cell(src_ws, r, 1)
            if a.startswith("B."):
                in_b = True
                continue
            if a.startswith("C."):
                break
            if in_b and _cell(src_ws, r, 4):
                ws.cell(out_r, 1).value = out_r - 15
                ws.cell(out_r, 2).value = _cell(src_ws, r, 2)
                ws.cell(out_r, 3).value = _cell(src_ws, r, 3)
                ws.cell(out_r, 4).value = _cell(src_ws, r, 4)
                ws.cell(out_r, 5).value = _cell(src_ws, r, 5)
                ws.cell(out_r, 6).value = _cell(src_ws, r, 6)
                out_r += 1
        idx += 1
    wb.save(DEST / "3. Tai lieu nghiep vu - Khao khi.xlsx")


def map_empty_04_05() -> None:
    shutil.copy(_slot(4), DEST / "4. Moc thoi gian.xlsx")
    shutil.copy(_slot(5), DEST / "5. Tai lieu gioi thieu.xlsx")


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    map_file01()
    map_file02()
    map_file03()
    map_empty_04_05()
    DBCL_DEST.mkdir(parents=True, exist_ok=True)
    for path in DEST.glob("*.xlsx"):
        shutil.copy(path, DBCL_DEST / path.name)
    print("wrote", DEST)
    print("wrote", DBCL_DEST)


if __name__ == "__main__":
    main()
