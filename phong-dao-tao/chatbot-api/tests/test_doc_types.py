from app.ingestion.doc_types import (
    CODE_MIXED,
    CODE_PROCEDURE,
    CODE_REGULATION,
    LABEL_MIXED,
    LABEL_PROCEDURE,
    LABEL_REGULATION,
    infer_doc_type,
    normalize_doc_type,
)
from app.ingestion.excel import parse_file03
from app.ingestion.issues import IssueLog
from tests.excel_fixtures import fill_file03


def test_normalize_three_labels() -> None:
    assert normalize_doc_type("Quy định") == (LABEL_REGULATION, CODE_REGULATION)
    assert normalize_doc_type("Thủ tục") == (LABEL_PROCEDURE, CODE_PROCEDURE)
    assert normalize_doc_type("Cả hai") == (LABEL_MIXED, CODE_MIXED)


def test_normalize_aliases() -> None:
    assert normalize_doc_type("Chính sách") == (LABEL_REGULATION, CODE_REGULATION)
    assert normalize_doc_type("Thông báo") == (LABEL_REGULATION, CODE_REGULATION)
    assert normalize_doc_type("Quy trình") == (LABEL_PROCEDURE, CODE_PROCEDURE)
    assert normalize_doc_type("Cả hai (quy định + thủ tục)") == (LABEL_MIXED, CODE_MIXED)


def test_unknown_doc_type() -> None:
    assert normalize_doc_type("Công văn") is None
    assert normalize_doc_type("") is None


def test_parse_maps_chinh_sach_to_quy_dinh() -> None:
    issues = IssueLog()
    docs, chunks = parse_file03(fill_file03(doc_type="Chính sách"), issues)
    assert issues.ok, issues.errors
    assert docs[0]["doc_type"] == LABEL_REGULATION
    assert docs[0]["doc_type_code"] == CODE_REGULATION
    assert chunks[0]["doc_type"] == LABEL_REGULATION


def test_unknown_loai_does_not_block() -> None:
    issues = IssueLog()
    docs, chunks = parse_file03(fill_file03(doc_type="Công văn"), issues)
    assert issues.ok, issues.errors
    assert docs[0]["doc_type"] == LABEL_REGULATION
    assert any(c["kind"] == "regulation" for c in chunks)


def test_file03_scans_regulation_and_procedure() -> None:
    issues = IssueLog()
    docs, chunks = parse_file03(fill_file03(procedure=True), issues)
    assert issues.ok, issues.errors
    kinds = {c["kind"] for c in chunks}
    assert {"regulation", "procedure_meta", "dossier", "step"} <= kinds
    assert docs[0]["doc_type"] == LABEL_MIXED
    assert docs[0]["doc_type_code"] == CODE_MIXED
    title = docs[0]["title"]
    assert all(title in c["text"] for c in chunks)


def test_infer_from_kinds() -> None:
    assert infer_doc_type({"regulation"}) == (LABEL_REGULATION, CODE_REGULATION)
    assert infer_doc_type({"step", "dossier"}) == (LABEL_PROCEDURE, CODE_PROCEDURE)
    assert infer_doc_type({"regulation", "step"}) == (LABEL_MIXED, CODE_MIXED)
