from app.gold.ids import gold_chunk_id, point_uuid
from app.gold.policy import boosted_score, is_effective, is_indexable
from app.gold.stair import (
    headings_related,
    serialize_condition,
    serialize_dossier,
    serialize_faq,
    serialize_procedure,
    serialize_regulation,
    serialize_step,
)


def test_faq_stair_keeps_question_and_marks_missing_basis() -> None:
    markdown = serialize_faq(
        question="Thời hạn phúc khảo ĐHCQ?",
        question_code="I.1.001",
        answer="Trong 2 ngày làm việc.",
        legal_basis=None,
        category="Phúc khảo",
        subcategory=None,
        release_status="approved_for_dev",
        source_file="2. FAQ.xlsx",
        source_sheet="1. FAQ",
        source_row=5,
    )
    assert "# Thời hạn phúc khảo ĐHCQ?" in markdown
    assert "I.1.001" in markdown
    assert "Phòng Bảo đảm chất lượng" in markdown
    assert "Khảo khí" in markdown
    assert "Chưa có văn bản căn cứ" in markdown
    assert "hotline" not in markdown.casefold()
    assert "phongbdcl@" not in markdown


def test_regulation_chunk_keeps_related_exception() -> None:
    markdown = serialize_regulation(
        document_title="Quy chế khảo thí",
        document_code="TL01",
        heading="Điện thoại trong phòng thi",
        subheading=None,
        content="Không mang điện thoại.",
        inline_condition=None,
        resolution="Vi phạm quy chế.",
        related_conditions=[
            ("exception", "Ngoại lệ máy tính bảng dùng cho thi", "Được phép khi giám thị cho")
        ],
        release_status="approved_for_dev",
        source_file="3. Tài liệu.xlsx",
        source_sheet="Tài liệu 1",
        source_row=10,
    )
    assert "Điện thoại trong phòng thi" in markdown
    assert "Ngoại lệ máy tính bảng" in markdown
    assert "Vi phạm quy chế" in markdown


def test_procedure_keeps_deadline_and_unknown_fee() -> None:
    markdown = serialize_procedure(
        document_title="Phúc khảo điểm",
        document_code="TL02",
        summary="Nộp đơn phúc khảo",
        result="Có kết quả phúc khảo",
        processing_time_type="working_days",
        max_working_days=7,
        location="Phòng BDCL",
        submission_url=None,
        special_schedule=None,
        fee_type="unknown",
        fee_amount_vnd=None,
        fee_note="Chưa xác định",
        answer_policy="insufficient_evidence",
        related_conditions=[("condition", "Áp dụng hệ SĐH", "Thời hạn 7 ngày làm việc")],
        release_status="approved_for_dev",
        effective_from=None,
        effective_to=None,
        source_file="3. Tài liệu.xlsx",
        source_sheet="Tài liệu 2",
        source_row=4,
    )
    assert "7 ngày làm việc" in markdown
    assert "Không nêu số tiền" in markdown
    assert "Áp dụng hệ SĐH" in markdown


def test_step_keeps_time_requirement_in_same_chunk() -> None:
    markdown = serialize_step(
        document_title="Nhận điểm I",
        document_code="TL03",
        step_number=1,
        instruction="Nộp đơn xin điểm I",
        time_requirement="Trong 3 ngày làm việc",
        url_or_location=None,
        responsible_unit=None,
        channel=None,
        release_status="approved_for_dev",
        source_file="3. Tài liệu.xlsx",
        source_sheet="Tài liệu 3",
        source_row=20,
    )
    assert "Bước 1" in markdown
    assert "3 ngày làm việc" in markdown
    assert "Nhận điểm I" in markdown


def test_condition_chunk_keeps_document_title() -> None:
    markdown = serialize_condition(
        document_title="Quy chế khảo thí",
        document_code="TL01",
        condition_type="exception",
        scenario="Mang điện thoại",
        resolution="Vi phạm",
        release_status="approved_for_dev",
        source_file="3. Tài liệu.xlsx",
        source_sheet="Tài liệu 1",
        source_row=40,
    )
    assert "Quy chế khảo thí" in markdown
    assert "Mang điện thoại" in markdown
    assert "Vi phạm" in markdown


def test_dossier_lists_required_items() -> None:
    markdown = serialize_dossier(
        document_title="Phúc khảo điểm",
        document_code="TL02",
        items=[("Đơn phúc khảo", "https://uel.edu.vn/form", "01 bản", True)],
        release_status="approved_for_dev",
        source_file="3. Tài liệu.xlsx",
        source_sheet="Tài liệu 2",
        source_row=12,
    )
    assert "Phúc khảo điểm — Hồ sơ" in markdown
    assert "Đơn phúc khảo" in markdown
    assert "bắt buộc" in markdown


def test_chunk_id_is_deterministic() -> None:
    first = gold_chunk_id("bao_dam_chat_luong", "khao_khi", "faq", "I.1.001")
    second = gold_chunk_id("bao_dam_chat_luong", "khao_khi", "faq", "I.1.001")
    other = gold_chunk_id("bao_dam_chat_luong", "khao_khi", "faq", "I.1.002")
    assert first == second
    assert first.startswith("gold:")
    assert first != other
    assert point_uuid(first) == point_uuid(second)


def test_index_policy_and_effective_dates() -> None:
    assert is_indexable(
        is_active=True, release_status="approved_for_dev", environment="development"
    )
    assert not is_indexable(is_active=True, release_status="approved_for_dev", environment="uat")
    assert not is_indexable(is_active=False, release_status="approved_for_uat", environment="uat")
    assert is_effective({"effective_from": None, "effective_to": None})
    assert headings_related("Phúc khảo", "Phúc khảo điểm thi ĐHCQ")
    assert boosted_score("faq", 0.5, 0.12) == 0.62
    assert boosted_score("regulation", 0.5, 0.12) == 0.5
