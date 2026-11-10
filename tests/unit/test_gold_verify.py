from app.gold.verify import count_entities, payload_has_pii


def test_payload_has_pii_detects_email_and_ignores_clean_stair() -> None:
    clean = {
        "entity_type": "faq",
        "stair_markdown": "# Phúc khảo\n\nTrong 2 ngày làm việc.\n",
        "department_id": "bao_dam_chat_luong",
    }
    dirty = {
        "entity_type": "faq",
        "stair_markdown": "Liên hệ phongbdcl@uel.edu.vn",
    }
    assert payload_has_pii(clean) is False
    assert payload_has_pii(dirty) is True


def test_count_entities() -> None:
    counts = count_entities(
        [
            {"entity_type": "faq"},
            {"entity_type": "faq"},
            {"entity_type": "regulation"},
        ]
    )
    assert counts == {"faq": 2, "regulation": 1}
