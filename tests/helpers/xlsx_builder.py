from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.ingestion.fingerprints import (
    extract_documents_schema,
    extract_faq_schema,
    extract_module_schema,
    schema_fingerprint,
)
from app.ingestion.normalize import sha256_file

# Re-export schema extractors for tests that need them after load.
__all__ = ["update_faq_answer", "write_mini_release"]


def _module_workbook(
    *,
    module_name: str,
    routing_rows: list[tuple[int, str, str]],
) -> Workbook:
    workbook = Workbook()
    guidance = workbook.active
    assert guidance is not None
    guidance.title = "0. Hướng dẫn"
    sheet = workbook.create_sheet("1. Phạm vi trả lời")
    sheet["A1"] = "PHẠM VI TRẢ LỜI CỦA MÔ-ĐUN"
    sheet["B3"] = "THÔNG TIN MÔ-ĐUN"
    sheet["B4"] = "Tên Mô-đun "
    sheet["C4"] = module_name
    sheet["B5"] = "Ngày tạo"
    sheet["C5"] = date(2026, 11, 8)
    sheet["B6"] = "Ngày cập nhật"
    sheet["C6"] = date(2026, 11, 8)
    headers = [
        "STT",
        "Phạm vi MÔ-ĐUN",
        "Chủ đề / tình huống",
        "Cách chatbot xử lý",
        "Đầu mối hỗ trợ (nếu cần)",
        "Thông tin liên hệ (nếu cần)",
        "Kênh trực tuyến (link Fanpage / Zalo / cổng ticket)",
    ]
    for column, header in enumerate(headers, start=1):
        sheet.cell(9, column, header)
    for offset, (order, scope, topic) in enumerate(routing_rows):
        row = 10 + offset
        sheet.cell(row, 1, order)
        sheet.cell(row, 2, scope)
        sheet.cell(row, 3, topic)
        if "cần cán bộ" in scope:
            sheet.cell(row, 5, "Phòng Bảo đảm chất lượng")
            sheet.cell(row, 6, "phongbdcl@uel.edu.vn | 19001239")
        if scope.startswith("Ngoài"):
            sheet.cell(row, 5, "Phòng Đào Tạo")
            sheet.cell(row, 6, "phongdaotao@uel.edu.vn | 19001239")
    sheet.cell(10 + len(routing_rows), 1, 99)
    return workbook


def _faq_workbook(rows: list[dict[str, str]]) -> Workbook:
    workbook = Workbook()
    guidance = workbook.active
    assert guidance is not None
    guidance.title = "0. Hướng dẫn"
    sheet = workbook.create_sheet("1. FAQ")
    headers = [
        "STT",
        "MÃ CÂU HỎI",
        "PHÂN MỤC",
        "PHÂN MỤC CHI TIẾT",
        "CÂU HỎI",
        "CÂU TRẢ LỜI",
        "VĂN BẢN CĂN CỨ (LOẠI, SỐ HIỆU, NGÀY BAN HÀNH) (NẾU CÓ)",
        "ĐẦU MỐI HỖ TRỢ (NẾU CẦN)",
        "THÔNG TIN LIÊN HỆ (NẾU CẦN)",
        "KÊNH TRỰC TUYẾN (NẾU CẦN)",
    ]
    for column, header in enumerate(headers, start=2):
        sheet.cell(4, column, header)
    for index, item in enumerate(rows):
        row = 5 + index
        sheet.cell(row, 2, str(index + 1))
        sheet.cell(row, 3, item["code"])
        sheet.cell(row, 4, item.get("category", "I. Quy định"))
        sheet.cell(row, 5, item.get("subcategory", "I.1"))
        sheet.cell(row, 6, item["question"])
        sheet.cell(row, 7, item.get("answer", "Câu trả lời mẫu."))
        if item.get("legal_basis"):
            sheet.cell(row, 8, item["legal_basis"])
    return workbook


def _fill_document_template(sheet: Worksheet, *, code: str, title: str, procedure: bool) -> None:
    sheet["C1"] = f"CHỦ ĐỀ {code}"
    sheet["A3"] = "A. THÔNG TIN CHUNG"
    sheet["B4"] = "Tên chủ đề "
    sheet["C4"] = title
    sheet["B5"] = "Tóm tắt (3-5 dòng) "
    sheet["C5"] = f"Tóm tắt {code}"
    sheet["B6"] = "Tên gọi khác / từ khóa"
    sheet["C6"] = f"{code.lower()}; khảo thí"
    sheet["A8"] = "B. NỘI DUNG QUY ĐỊNH "
    regulation_headers = [
        "STT",
        "Phân mục",
        "Phân mục chi tiết",
        " Nội dung",
        "Tình huống / điều kiện (nếu có)",
        "Cách xử lý / kết luận (nếu có)",
    ]
    for column, header in enumerate(regulation_headers, start=1):
        sheet.cell(9, column, header)
    sheet["A10"] = 1
    sheet["B10"] = "Điều kiện thực hiện"
    sheet["D10"] = f"Nội dung quy định của {code}."
    sheet["A21"] = "C. ĐIỀU KIỆN, NGOẠI LỆ, LỖI THƯỜNG GẶP"
    sheet["A22"] = "STT"
    sheet["B22"] = "Tình huống / điều kiện"
    sheet["D22"] = "Cách xử lý / kết luận"
    sheet["E22"] = "Loại"
    sheet["A23"] = 1
    sheet["B23"] = "Tình huống mẫu"
    sheet["D23"] = "Cách xử lý mẫu"
    sheet["E23"] = "Lưu ý"
    sheet["A34"] = "D. THỰC HIỆN THỦ TỤC"
    labels = [
        "Kết quả người học nhận được (nếu chọn thủ tục)",
        "Thời hạn xử lý (nếu chọn thủ tục)",
        "Số ngày làm việc (tối đa) (nếu chọn N ngày)",
        "Địa điểm (phòng / tòa nhà)",
        "Link nộp / cổng trực tuyến",
        "Lịch tiếp nhận đặc biệt",
        "Lệ phí (nếu chọn thủ tục)",
        "Số tiền (VNĐ) (nếu thu phí cố định)",
        "Ghi chú lệ phí / hình thức nộp",
    ]
    for offset, label in enumerate(labels):
        sheet.cell(35 + offset, 2, label)
    if procedure:
        sheet["C35"] = "Kết quả thủ tục"
        sheet["C36"] = "N ngày làm việc"
        sheet["C37"] = "10"
        sheet["C38"] = "Portal UEL"
        sheet["C39"] = "https://portal.uel.edu.vn/"
        sheet["C43"] = "Lệ phí phúc khảo: Chưa xác định trong nguồn được rà soát"
    sheet["A45"] = "E. HỒ SƠ CẦN CHUẨN BỊ "
    dossier_headers = [
        "STT",
        "Thành phần hồ sơ",
        "Mã biểu mẫu & link tải (URL)",
        "Số lượng & quy cách",
        "Bắt buộc",
    ]
    for column, header in enumerate(dossier_headers, start=1):
        sheet.cell(46, column, header)
    if procedure:
        sheet["A47"] = 1
        sheet["B47"] = "Đơn đăng ký"
        sheet["C47"] = "https://portal.uel.edu.vn/"
        sheet["D47"] = "01"
        sheet["E47"] = "Có"
    sheet["A58"] = "F. CÁC BƯỚC THỰC HIỆN "
    step_headers = [
        "Bước",
        "Người học làm gì",
        "Link / địa điểm",
        "Đơn vị tiếp nhận / xử lý",
        "Thời gian",
        "Kênh",
    ]
    for column, header in enumerate(step_headers, start=1):
        sheet.cell(59, column, header)
    if procedure:
        sheet["A60"] = 1
        sheet["B60"] = "Đăng nhập Portal"
        sheet["C60"] = "https://portal.uel.edu.vn/"
        sheet["D60"] = "Phòng Bảo đảm chất lượng"
        sheet["E60"] = "Theo quy trình"
        sheet["F60"] = "Portal"


def _documents_workbook() -> Workbook:
    workbook = Workbook()
    guidance = workbook.active
    assert guidance is not None
    guidance.title = "Hướng dẫn"
    specs = [
        ("Tài liệu 1", "TL01", "Quy định khảo thí", False),
        ("Tài liệu 2", "TL02", "Phúc khảo", True),
        ("Tài liệu 3", "TL03", "Hoãn thi", True),
        ("Tài liệu 4", "TL04", "Trả điểm I", True),
    ]
    for name, code, title, procedure in specs:
        _fill_document_template(
            workbook.create_sheet(name), code=code, title=title, procedure=procedure
        )
    workbook.create_sheet("MẪU").sheet_state = "hidden"
    workbook.create_sheet("_DS").sheet_state = "hidden"
    return workbook


def write_mini_release(
    directory: Path,
    *,
    duplicate_faq: bool = False,
    invalid_scope: bool = False,
    module_name: str = "Mô-đun Khảo khí",
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    routing = [
        (1, "Trong phạm vi trả lời", "Quy định hình thức thi"),
        (2, "Trong phạm vi - bot không tự trả lời & cần cán bộ hỗ trợ", "Kết quả cá nhân"),
        (3, "Ngoài phạm vi trả lời", "Học phí"),
    ]
    if invalid_scope:
        routing[0] = (1, "Phạm vi lạ", "Quy định hình thức thi")
    faqs = [
        {
            "code": "I.1.001",
            "question": "Quy định khảo thí ở đâu?",
            "answer": "Theo Quyết định 3388.",
            "legal_basis": "Quyết định số 3388/QĐ-ĐHKTL",
        },
        {
            "code": "I.1.002" if not duplicate_faq else "I.1.001",
            "question": "Thời hạn phúc khảo?",
            "answer": "Hai ngày làm việc.",
        },
    ]
    files = {
        "1. Thông tin Mô-đun - Khảo khí.xlsx": _module_workbook(
            module_name=module_name,
            routing_rows=routing,
        ),
        "2. FAQ - Câu hỏi thường gặp.xlsx": _faq_workbook(faqs),
        "3. Tài liệu nghiệp vụ.xlsx": _documents_workbook(),
    }
    saved: dict[str, Path] = {}
    fingerprints: dict[str, dict[str, str]] = {}
    extractors = {
        "1. Thông tin Mô-đun - Khảo khí.xlsx": extract_module_schema,
        "2. FAQ - Câu hỏi thường gặp.xlsx": extract_faq_schema,
        "3. Tài liệu nghiệp vụ.xlsx": extract_documents_schema,
    }
    roles = {
        "1. Thông tin Mô-đun - Khảo khí.xlsx": "module_and_routing",
        "2. FAQ - Câu hỏi thường gặp.xlsx": "faq",
        "3. Tài liệu nghiệp vụ.xlsx": "business_documents",
    }
    for name, workbook in files.items():
        path = directory / name
        workbook.save(path)
        saved[name] = path
        fingerprints[name] = {
            "file_sha256": sha256_file(path),
            "schema_sha256": schema_fingerprint(extractors[name](workbook)),
            "role": roles[name],
        }
    manifest = {
        "schema_version": "1.0",
        "release_id": "mini-khao-khi-test",
        "created_at": "2026-11-10",
        "department": {"id": "bao_dam_chat_luong", "name": "Phòng Bảo đảm chất lượng"},
        "module": {"code": "khao_khi", "name": "Mô-đun Khảo khí"},
        "source_type": "xlsx",
        "release_status": "approved_for_dev",
        "files": [
            {
                "name": name,
                "role": meta["role"],
                "file_sha256": meta["file_sha256"],
                "schema_sha256": meta["schema_sha256"],
            }
            for name, meta in fingerprints.items()
        ],
        "expected_counts": {
            "routing_rules": 3,
            "faqs": 2,
            "documents": 4,
            "regulation_sections": 4,
            "condition_exception_sections": 4,
            "dossier_items": 3,
            "procedure_steps": 3,
        },
        "allowed_environments": ["development", "test"],
        "prohibited_environments": ["uat", "production"],
    }
    (directory / "release-manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    config = {
        "schema_version": "1.0",
        "departments": [
            {
                "id": "bao_dam_chat_luong",
                "name": "Phòng Bảo đảm chất lượng",
                "audience": "nguoi_hoc",
                "enabled": True,
                "contact": {
                    "support_contact": "Phòng Bảo đảm chất lượng",
                    "contact_information": "phongbdcl@uel.edu.vn | 19001239",
                    "verified": False,
                },
                "modules": [
                    {
                        "code": "khao_khi",
                        "name": "Mô-đun Khảo khí",
                        "source_type": "xlsx",
                        "source_path": str(directory),
                        "enabled": True,
                        "contact": {
                            "support_contact": "Phòng Bảo đảm chất lượng",
                            "contact_information": "phongbdcl@uel.edu.vn | 19001239",
                            "verified": False,
                        },
                    }
                ],
            }
        ],
    }
    config_path = directory / "departments.yaml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return config_path


def update_faq_answer(directory: Path, question_code: str, answer: str) -> None:
    path = directory / "2. FAQ - Câu hỏi thường gặp.xlsx"
    workbook = load_workbook(path)
    sheet = workbook["1. FAQ"]
    for row in range(5, sheet.max_row + 1):
        if str(sheet.cell(row, 3).value or "") == question_code:
            sheet.cell(row, 7, answer)
            break
    workbook.save(path)
    manifest_path = directory / "release-manifest.yaml"
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    for item in payload["files"]:
        if item["role"] == "faq":
            item["file_sha256"] = sha256_file(path)
    manifest_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
