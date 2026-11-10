from app.ingestion.contact import ContactConfig, resolve_contact
from app.ingestion.enums import CANONICAL_DEPARTMENT_NAME
from app.ingestion.keys import section_key


def test_record_contact_wins_over_defaults() -> None:
    resolved = resolve_contact(
        record_support="Cán bộ A",
        record_information="a@uel.edu.vn",
        record_channel=None,
        module=ContactConfig(support_contact="Module", verified=True),
        department=ContactConfig(support_contact="Department", verified=True),
        allow_unverified_inheritance=True,
    )
    assert resolved.source == "record"
    assert resolved.support_contact == "Cán bộ A"


def test_unverified_module_contact_inherited_only_in_development() -> None:
    module = ContactConfig(
        support_contact=CANONICAL_DEPARTMENT_NAME,
        contact_information="phongbdcl@uel.edu.vn | 19001239",
        verified=False,
    )
    department = ContactConfig()
    inherited = resolve_contact(
        record_support=None,
        record_information=None,
        record_channel=None,
        module=module,
        department=department,
        allow_unverified_inheritance=True,
    )
    blocked = resolve_contact(
        record_support=None,
        record_information=None,
        record_channel=None,
        module=module,
        department=department,
        allow_unverified_inheritance=False,
    )
    assert inherited.source == "module"
    assert inherited.verified is False
    assert blocked.source == "none"
    assert blocked.support_contact is None


def test_section_key_is_stable_for_same_heading() -> None:
    first = section_key("TL01", "regulation", "Hình thức thi", 1)
    second = section_key("TL01", "regulation", "Hình thức thi", 1)
    changed = section_key("TL01", "regulation", "Hình thức thi (sửa)", 1)
    assert first == second
    assert first.startswith("section:")
    assert first != changed
