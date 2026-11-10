from __future__ import annotations

import hashlib
import uuid


def gold_chunk_id(
    department_id: str,
    module_code: str,
    entity_type: str,
    business_key: str,
) -> str:
    digest = hashlib.sha256(
        f"{department_id}|{module_code}|{entity_type}|{business_key}".encode()
    ).hexdigest()
    return f"gold:{digest[:24]}"


def point_uuid(chunk_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)
