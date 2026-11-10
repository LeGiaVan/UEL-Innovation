from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

_LEADING_TRAILING_PUNCTUATION = " \t.,;:!?…“”\"'"
_URL_PATTERN = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
_HOTLINE_PATTERN = re.compile(r"\b(?:\+?84|0|1900)\d{6,11}\b")


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def normalize_space(value: str) -> str:
    return " ".join(nfc(value).split())


def normalize_rich_text(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", nfc(line)).strip() for line in value.splitlines()]
    return "\n".join(lines).strip()


def optional_text(value: object, *, multiline: bool = False) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        text = value.date().isoformat()
    elif isinstance(value, date):
        text = value.isoformat()
    else:
        text = str(value)
    cleaned = normalize_rich_text(text) if multiline else normalize_space(text)
    return cleaned or None


def optional_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = normalize_space(str(value))
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def optional_int(value: object) -> int | None:
    text = optional_text(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def normalize_question(value: str) -> str:
    text = normalize_space(value).lower()
    return text.strip(_LEADING_TRAILING_PUNCTUATION)


def content_hash(*parts: str | None) -> str:
    payload = "|".join(part or "" for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path | str) -> str:
    return sha256_bytes(Path(path).read_bytes())


def extract_urls(value: str | None) -> list[str]:
    if not value:
        return []
    return [match.rstrip(".,;") for match in _URL_PATTERN.findall(value)]


def extract_emails(value: str | None) -> list[str]:
    if not value:
        return []
    return _EMAIL_PATTERN.findall(value)


def looks_like_url(value: str) -> bool:
    compact = value.strip()
    return compact.startswith("http://") or compact.startswith("https://")


def is_valid_http_url(value: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def extract_hotlines(value: str | None) -> list[str]:
    if not value:
        return []
    compact = value.replace(" ", "")
    return _HOTLINE_PATTERN.findall(compact)


def redact_contact_text(value: str) -> str:
    redacted = _EMAIL_PATTERN.sub("[email đã ẩn]", value)
    return _HOTLINE_PATTERN.sub("[số liên hệ đã ẩn]", redacted)
