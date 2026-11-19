from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def load_window(db, *, sub: str, kind: str) -> dict[str, Any] | None:
    return db["rate_windows"].find_one({"sub": sub, "kind": kind})


def save_window(db, *, sub: str, kind: str, stamps: list[datetime], now: datetime) -> None:
    db["rate_windows"].update_one(
        {"sub": sub, "kind": kind},
        {"$set": {"stamps": stamps, "updated_at": now}},
        upsert=True,
    )


def window_stamps(doc: dict[str, Any] | None) -> list[datetime]:
    if not doc:
        return []
    out: list[datetime] = []
    for item in doc.get("stamps") or []:
        if isinstance(item, datetime):
            out.append(_as_utc(item))
    return out


def get_daily_tokens(db, *, sub: str, day: str) -> int:
    doc = db["token_daily"].find_one({"sub": sub, "day": day})
    if not doc:
        return 0
    return int(doc.get("tokens") or 0)


def add_daily_tokens(db, *, sub: str, day: str, tokens: int, now: datetime) -> None:
    db["token_daily"].update_one(
        {"sub": sub, "day": day},
        {"$inc": {"tokens": int(tokens)}, "$set": {"updated_at": now}},
        upsert=True,
    )
