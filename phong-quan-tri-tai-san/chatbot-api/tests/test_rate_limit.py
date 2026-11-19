from datetime import datetime, timedelta, timezone

from app.services.rate_limit_service import (
    ADMIN_TRIAL_PER_MINUTE,
    ICT,
    add_llm_tokens,
    ict_day,
    word_count,
)
from tests.conftest import logged_in_client


FIXED = datetime(2026, 11, 18, 12, 0, tzinfo=ICT)


def _chat(client, message="xin chào", trial=False):
    return client.post("/api/chat/stream", json={"message": message, "trial": trial})


def test_word_count_split() -> None:
    assert word_count("xin chào") == 2
    assert word_count("  a   b c  ") == 3
    assert word_count("x " * 1000) == 1000
    assert word_count("x " * 1001) == 1001


def test_over_1000_words_returns_400() -> None:
    client = logged_in_client(email="sv@gmail.com")
    client.app.state.now_fn = lambda: FIXED
    res = _chat(client, ("từ " * 1001).strip())
    assert res.status_code == 400
    assert "1000" in res.json()["detail"]


def test_exactly_1000_words_ok() -> None:
    client = logged_in_client(email="sv@gmail.com")
    client.app.state.now_fn = lambda: FIXED
    res = _chat(client, ("từ " * 1000).strip())
    assert res.status_code == 200


def test_member_rpm_returns_429_retry_after() -> None:
    client = logged_in_client(email="sv@gmail.com")
    client.app.state.now_fn = lambda: FIXED
    client.app.state.department["rate_limit"] = {
        "chats_per_minute": 2,
        "llm_tokens_per_day": 50000,
    }
    assert _chat(client).status_code == 200
    assert _chat(client).status_code == 200
    res = _chat(client)
    assert res.status_code == 429
    assert res.headers.get("retry-after")
    assert int(res.headers["retry-after"]) >= 1


def test_daily_tokens_block_next_turn_not_current() -> None:
    client = logged_in_client(email="sv@gmail.com")
    client.app.state.now_fn = lambda: FIXED
    client.app.state.department["rate_limit"] = {
        "chats_per_minute": 10,
        "llm_tokens_per_day": 100,
    }
    me = client.get("/api/auth/me").json()
    assert _chat(client).status_code == 200
    add_llm_tokens(client.app.state.db, sub=me["sub"], tokens=100, now=FIXED)
    res = _chat(client)
    assert res.status_code == 429
    assert "token" in res.json()["detail"].lower()
    retry = int(res.headers["retry-after"])
    assert retry > 0
    # stub P2 không trừ token ngày (không LLM)
    assert ict_day(FIXED) == "2026-11-18"


def test_daily_resets_at_ict_midnight() -> None:
    client = logged_in_client(email="sv@gmail.com")
    client.app.state.department["rate_limit"] = {
        "chats_per_minute": 10,
        "llm_tokens_per_day": 50,
    }
    me = client.get("/api/auth/me").json()
    client.app.state.now_fn = lambda: FIXED
    add_llm_tokens(client.app.state.db, sub=me["sub"], tokens=50, now=FIXED)
    assert _chat(client).status_code == 429

    nxt = FIXED + timedelta(days=1)
    client.app.state.now_fn = lambda: nxt
    assert _chat(client).status_code == 200


def test_stub_stream_does_not_consume_daily_tokens() -> None:
    client = logged_in_client(email="sv@gmail.com")
    client.app.state.now_fn = lambda: FIXED
    client.app.state.department["rate_limit"] = {
        "chats_per_minute": 10,
        "llm_tokens_per_day": 1,
    }
    me = client.get("/api/auth/me").json()
    assert _chat(client).status_code == 200
    assert _chat(client).status_code == 200
    from app.repositories.rate_limit import get_daily_tokens

    assert get_daily_tokens(client.app.state.db, sub=me["sub"], day="2026-11-18") == 0


def test_admin_trial_skips_member_daily_and_has_own_rpm() -> None:
    client = logged_in_client(email="boss@uel.edu.vn", admins=["boss@uel.edu.vn"])
    client.app.state.now_fn = lambda: FIXED
    client.app.state.department["rate_limit"] = {
        "chats_per_minute": 2,
        "llm_tokens_per_day": 1,
    }
    me = client.get("/api/auth/me").json()
    add_llm_tokens(client.app.state.db, sub=me["sub"], tokens=1, now=FIXED)
    for _ in range(3):
        assert _chat(client, trial=True).status_code == 200
    for _ in range(ADMIN_TRIAL_PER_MINUTE - 3):
        assert _chat(client, trial=True).status_code == 200
    res = _chat(client, trial=True)
    assert res.status_code == 429
    assert res.headers.get("retry-after")


def test_member_trial_forbidden() -> None:
    client = logged_in_client(email="sv@gmail.com")
    client.app.state.now_fn = lambda: FIXED
    res = _chat(client, trial=True)
    assert res.status_code == 403


def test_admin_public_chat_does_not_eat_member_quota() -> None:
    """Admin hỏi trên chat thường: trần 20/phút, không trừ token ngày member."""
    client = logged_in_client(email="boss@uel.edu.vn", admins=["boss@uel.edu.vn"])
    client.app.state.now_fn = lambda: FIXED
    client.app.state.department["rate_limit"] = {
        "chats_per_minute": 1,
        "llm_tokens_per_day": 1,
    }
    me = client.get("/api/auth/me").json()
    add_llm_tokens(client.app.state.db, sub=me["sub"], tokens=1, now=FIXED)
    assert _chat(client).status_code == 200
    assert _chat(client).status_code == 200
