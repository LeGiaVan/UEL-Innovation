from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.ingestion.enums import CANONICAL_DEPARTMENT_NAME

ContactSource = Literal["record", "module", "department", "none"]


class ContactConfig(BaseModel):
    support_contact: str | None = None
    contact_information: str | None = None
    online_channel: str | None = None
    verified: bool = False


class ResolvedContact(BaseModel):
    support_contact: str | None = None
    contact_information: str | None = None
    online_channel: str | None = None
    source: ContactSource = "none"
    verified: bool = False


def resolve_contact(
    *,
    record_support: str | None,
    record_information: str | None,
    record_channel: str | None,
    module: ContactConfig,
    department: ContactConfig,
    allow_unverified_inheritance: bool,
) -> ResolvedContact:
    """Resolve contact using record → confirmed module → confirmed department.

    Unverified module/department defaults are inherited only when
    ``allow_unverified_inheritance`` is true (development/test).
    """

    if record_support or record_information or record_channel:
        return ResolvedContact(
            support_contact=record_support,
            contact_information=record_information,
            online_channel=record_channel,
            source="record",
            verified=False,
        )
    if module.verified or (allow_unverified_inheritance and _has_contact(module)):
        if _has_contact(module):
            return ResolvedContact(
                support_contact=module.support_contact,
                contact_information=module.contact_information,
                online_channel=module.online_channel,
                source="module",
                verified=module.verified,
            )
    if department.verified or (allow_unverified_inheritance and _has_contact(department)):
        if _has_contact(department):
            return ResolvedContact(
                support_contact=_canonical_unit(department.support_contact),
                contact_information=department.contact_information,
                online_channel=department.online_channel,
                source="department",
                verified=department.verified,
            )
    return ResolvedContact()


def _has_contact(config: ContactConfig) -> bool:
    return bool(config.support_contact or config.contact_information or config.online_channel)


def _canonical_unit(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.casefold()
    if "bảo đảm chất lượng" in lowered or "bao dam chat luong" in lowered.replace("đ", "d"):
        return CANONICAL_DEPARTMENT_NAME
    return value
