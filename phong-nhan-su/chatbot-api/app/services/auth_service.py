from __future__ import annotations

from typing import Any

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


class GoogleTokenError(ValueError):
    pass


def verify_google_id_token(token: str, client_id: str) -> dict[str, Any]:
    if not client_id:
        raise GoogleTokenError("GOOGLE_CLIENT_ID is not configured")
    if not token:
        raise GoogleTokenError("missing id_token")
    try:
        info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=client_id,
        )
    except Exception as exc:  # noqa: BLE001 — Google lib raises many types
        raise GoogleTokenError("invalid Google ID token") from exc
    if not info.get("email"):
        raise GoogleTokenError("token missing email")
    if not info.get("email_verified"):
        raise GoogleTokenError("email is not verified")
    if not info.get("sub"):
        raise GoogleTokenError("token missing sub")
    return info
