from app.ingestion.normalize import (
    is_valid_http_url,
    normalize_question,
    normalize_space,
    optional_text,
    redact_contact_text,
)


def test_normalize_space_uses_unicode_nfc() -> None:
    decomposed = "Khảo khí"
    assert normalize_space(decomposed) == "Khảo khí"
    assert optional_text("  phúc   khảo  ") == "phúc khảo"


def test_normalize_question_strips_edge_punctuation() -> None:
    assert normalize_question("Thời hạn phúc khảo?") == "thời hạn phúc khảo"


def test_redact_contact_text_hides_email() -> None:
    text = redact_contact_text("Gửi đơn tới phongbdcl@uel.edu.vn trước hạn.")
    assert "phongbdcl@uel.edu.vn" not in text
    assert "[email đã ẩn]" in text


def test_url_validation() -> None:
    assert is_valid_http_url("https://portal.uel.edu.vn/")
    assert not is_valid_http_url("ftp://example.com")
    assert not is_valid_http_url("not-a-url")
