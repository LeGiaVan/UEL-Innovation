from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

COOKIE_NAME = "uel_session"
JWT_ALG = "HS256"


def resolve_role(
    email: str,
    admins: list[str] | None,
    *,
    allow_non_uel_admin: bool = False,
) -> str:
    normalized = (email or "").strip().lower()
    allow = {(a or "").strip().lower() for a in (admins or []) if a}
    if normalized not in allow:
        return "member"
    if normalized.endswith("@uel.edu.vn") or allow_non_uel_admin:
        return "department_admin"
    return "member"


def encode_session_jwt(
    *,
    secret: str,
    sub: str,
    email: str,
    role: str,
    department_id: str,
    sid: str,
    ttl_hours: int,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "department_id": department_id,
        "sid": sid,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALG)


def decode_session_jwt(token: str, secret: str) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=[JWT_ALG])
