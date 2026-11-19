from __future__ import annotations

from urllib.parse import urlparse

LOCAL_DEV_ORIGINS = (
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def normalize_origin(value: str) -> str:
    raw = (value or "").strip().rstrip("/")
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    return raw.lower()


def allowed_origins(settings, department: dict | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def add(raw: str) -> None:
        origin = normalize_origin(raw)
        if origin and origin not in seen:
            seen.add(origin)
            out.append(origin)

    for origin in LOCAL_DEV_ORIGINS:
        add(origin)
    extra = getattr(settings, "cors_origins", "") or ""
    for part in str(extra).split(","):
        add(part)
    domain = str((department or {}).get("domain") or "").strip()
    if domain and domain.lower() not in {"localhost", "127.0.0.1"}:
        add(f"https://{domain}")
        if not bool(getattr(settings, "cookie_secure", False)):
            add(f"http://{domain}")
    return out


def origin_from_headers(origin_header: str, referer_header: str) -> str:
    origin = normalize_origin(origin_header)
    if origin:
        return origin
    referer = (referer_header or "").strip()
    if not referer:
        return ""
    parsed = urlparse(referer)
    if parsed.scheme and parsed.netloc:
        return normalize_origin(f"{parsed.scheme}://{parsed.netloc}")
    return ""


def origin_allowed(origin: str, allowed: list[str]) -> bool:
    if not origin:
        return False
    return normalize_origin(origin) in {normalize_origin(item) for item in allowed}
