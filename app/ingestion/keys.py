from __future__ import annotations

import hashlib

from app.ingestion.normalize import normalize_space


def section_key(
    document_code: str,
    section_type: str,
    heading: str | None,
    source_order: int | None,
) -> str:
    normalized = normalize_space(heading or "").lower()
    digest = hashlib.sha256(
        f"{document_code}|{section_type}|{normalized}|{source_order or 0}".encode()
    ).hexdigest()
    return f"section:{digest[:20]}"
