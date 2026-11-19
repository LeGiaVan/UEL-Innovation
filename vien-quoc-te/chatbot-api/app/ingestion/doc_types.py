"""Nhãn Loại File 03 — tùy chọn. Parser quét hết B–F; mã suy ra từ chunk có mặt."""

from __future__ import annotations

import re

from app.ingestion.normalize import nfc_lower

LABEL_REGULATION = "Quy định"
LABEL_PROCEDURE = "Thủ tục"
LABEL_MIXED = "Cả hai"

CODE_REGULATION = "regulation"
CODE_PROCEDURE = "procedure"
CODE_MIXED = "mixed"

DOC_TYPE_LABELS: dict[str, str] = {
    CODE_REGULATION: LABEL_REGULATION,
    CODE_PROCEDURE: LABEL_PROCEDURE,
    CODE_MIXED: LABEL_MIXED,
}

DOC_TYPE_CODES: tuple[str, ...] = (CODE_REGULATION, CODE_PROCEDURE, CODE_MIXED)
DOC_TYPE_DROPDOWN: tuple[str, ...] = (LABEL_REGULATION, LABEL_PROCEDURE, LABEL_MIXED)

_REGULATION_KINDS = frozenset({"regulation"})
_PROCEDURE_KINDS = frozenset({"procedure_meta", "dossier", "step"})

_ALIASES: dict[str, str] = {
    "quy định": CODE_REGULATION,
    "quy dinh": CODE_REGULATION,
    "chính sách": CODE_REGULATION,
    "chinh sach": CODE_REGULATION,
    "thông báo": CODE_REGULATION,
    "thong bao": CODE_REGULATION,
    "hướng dẫn": CODE_REGULATION,
    "huong dan": CODE_REGULATION,
    "quyết định": CODE_REGULATION,
    "quyet dinh": CODE_REGULATION,
    "thủ tục": CODE_PROCEDURE,
    "thu tuc": CODE_PROCEDURE,
    "quy trình": CODE_PROCEDURE,
    "quy trinh": CODE_PROCEDURE,
    "cả hai": CODE_MIXED,
    "ca hai": CODE_MIXED,
    "cả hai (quy định + thủ tục)": CODE_MIXED,
    "ca hai (quy dinh + thu tuc)": CODE_MIXED,
    "quy định + thủ tục": CODE_MIXED,
    "quy dinh + thu tuc": CODE_MIXED,
}


def _fold(raw: str) -> str:
    return re.sub(r"\s+", " ", nfc_lower(raw))


def normalize_doc_type(raw: str) -> tuple[str, str] | None:
    """Trả (nhãn Excel, mã nội bộ) hoặc None nếu không nhận."""
    key = _fold(raw)
    if not key:
        return None
    code = _ALIASES.get(key)
    if not code:
        return None
    return DOC_TYPE_LABELS[code], code


def infer_doc_type(kinds: set[str]) -> tuple[str, str]:
    """Suy Loại từ mục đã có dữ liệu — không đọc dropdown."""
    has_reg = bool(kinds & _REGULATION_KINDS)
    has_proc = bool(kinds & _PROCEDURE_KINDS)
    if has_reg and has_proc:
        return LABEL_MIXED, CODE_MIXED
    if has_proc:
        return LABEL_PROCEDURE, CODE_PROCEDURE
    return LABEL_REGULATION, CODE_REGULATION
