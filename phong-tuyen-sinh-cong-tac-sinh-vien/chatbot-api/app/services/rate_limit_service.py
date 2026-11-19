from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from math import ceil

from app.repositories import rate_limit as repo

ICT = timezone(timedelta(hours=7))
MAX_WORDS = 1000
ADMIN_TRIAL_PER_MINUTE = 20
DEFAULT_CHATS_PER_MINUTE = 10
DEFAULT_LLM_TOKENS_PER_DAY = 50_000
WINDOW_SEC = 60


@dataclass(frozen=True)
class GateFail:
    status: int
    detail: str
    retry_after: int | None = None


def word_count(text: str) -> int:
    return len((text or "").split())


def ict_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(ICT)


def ict_day(now: datetime | None = None) -> str:
    return ict_now(now).date().isoformat()


def seconds_until_ict_midnight(now: datetime | None = None) -> int:
    current = ict_now(now)
    nxt = datetime.combine(current.date() + timedelta(days=1), time.min, tzinfo=ICT)
    return max(1, int(ceil((nxt - current).total_seconds())))


def _rate_cfg(department: dict | None) -> tuple[int, int]:
    cfg = (department or {}).get("rate_limit") or {}
    rpm = int(cfg.get("chats_per_minute") or DEFAULT_CHATS_PER_MINUTE)
    daily = int(cfg.get("llm_tokens_per_day") or DEFAULT_LLM_TOKENS_PER_DAY)
    return max(1, rpm), max(1, daily)


def add_llm_tokens(db, *, sub: str, tokens: int, now: datetime | None = None) -> None:
    """P4 gọi sau LLM. FAQ/regex/cosine không gọi. Lượt đang chạy vẫn trả lời."""
    if db is None or tokens <= 0 or not sub:
        return
    current = ict_now(now).astimezone(timezone.utc)
    repo.add_daily_tokens(db, sub=sub, day=ict_day(current), tokens=tokens, now=current)


def check_chat_limits(
    db,
    *,
    user: dict,
    message: str,
    department: dict | None,
    trial: bool = False,
    now: datetime | None = None,
) -> GateFail | None:
    if word_count(message) > MAX_WORDS:
        return GateFail(status=400, detail=f"Câu hỏi vượt quá {MAX_WORDS} từ")

    role = user.get("role")
    if trial and role != "department_admin":
        return GateFail(status=403, detail="Chỉ quản trị phòng được thử chat")

    if db is None:
        return GateFail(status=503, detail="MongoDB chưa sẵn sàng — chạy mongo rồi thử lại")

    current = ict_now(now).astimezone(timezone.utc)
    sub = str(user.get("sub") or "")
    is_admin = role == "department_admin"
    rpm, daily_cap = _rate_cfg(department)
    kind = "admin_trial" if is_admin else "member"
    limit = ADMIN_TRIAL_PER_MINUTE if is_admin else rpm

    stamps = [
        ts
        for ts in repo.window_stamps(repo.load_window(db, sub=sub, kind=kind))
        if (current - ts).total_seconds() < WINDOW_SEC
    ]
    if len(stamps) >= limit:
        oldest = min(stamps)
        retry = max(1, int(ceil(WINDOW_SEC - (current - oldest).total_seconds())))
        return GateFail(
            status=429,
            detail="Vượt số lượt hỏi trong một phút",
            retry_after=retry,
        )

    if not is_admin:
        used = repo.get_daily_tokens(db, sub=sub, day=ict_day(current))
        if used >= daily_cap:
            return GateFail(
                status=429,
                detail="Đã hết hạn mức token LLM trong ngày",
                retry_after=seconds_until_ict_midnight(current),
            )

    stamps.append(current)
    repo.save_window(db, sub=sub, kind=kind, stamps=stamps, now=current)
    return None
