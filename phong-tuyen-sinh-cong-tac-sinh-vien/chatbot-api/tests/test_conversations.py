from app.services.conversation_service import (
    get_conversation,
    list_conversations,
    load_history,
    save_turn,
    summarize_chat_turns,
)
from tests.conftest import FakeDB


def test_save_turn_writes_chat_turns_for_analytics() -> None:
    db = FakeDB()
    cid = save_turn(
        db,
        sub="google-1",
        email="sv@gmail.com",
        conversation_id=None,
        module_code="khao_khi",
        department_id="starter",
        user_message="trả điểm I như nào",
        answer="Trong hạn 01 năm.",
        routing_source="cosine",
        status="answer_allowed",
        rule_id="khao_khi.diem-i",
        citations=[{"title": "Quy định"}],
        release_id="r1",
        llm_tokens=42,
        latency_ms=15,
        trial=False,
        user_agent="pytest-analytics",
    )
    save_turn(
        db,
        sub="google-1",
        email="sv@gmail.com",
        conversation_id=cid,
        module_code="khao_khi",
        department_id="starter",
        user_message="hệ chính quy thì sao",
        answer="Cùng hạn.",
        routing_source="regex",
        status="answer_allowed",
        release_id="r1",
        llm_tokens=8,
        latency_ms=9,
        trial=False,
    )
    save_turn(
        db,
        sub="google-2",
        email="other@gmail.com",
        conversation_id=None,
        module_code="thong_tin_chung",
        department_id="starter",
        user_message="học phí ở đâu",
        answer="Ngoài phạm vi.",
        routing_source="regex",
        status="out_of_scope",
        release_id="r2",
        llm_tokens=4,
        latency_ms=6,
        trial=False,
    )
    turns = sorted(
        db["chat_turns"].find({"conversation_id": cid}),
        key=lambda row: row["turn_index"],
    )
    assert [row["turn_index"] for row in turns] == [1, 2]
    first = turns[0]
    assert first["conversation_id"] == cid
    assert first["sub"] == "google-1"
    assert first["email"] == "sv@gmail.com"
    assert first["department_id"] == "starter"
    assert first["module_code"] == "khao_khi"
    assert first["release_id"] == "r1"
    assert first["user_message"] == "trả điểm I như nào"
    assert first["assistant_answer"] == "Trong hạn 01 năm."
    assert first["routing_source"] == "cosine"
    assert first["status"] == "answer_allowed"
    assert first["rule_id"] == "khao_khi.diem-i"
    assert first["citation_count"] == 1
    assert first["llm_tokens"] == 42
    assert first["latency_ms"] == 15
    assert first["trial"] is False
    assert first["user_agent"] == "pytest-analytics"
    conv = db["conversations"].find_one({"id": cid})
    assert conv["turn_count"] == 2
    assert conv["last_status"] == "answer_allowed"
    msgs = db["messages"].find({"conversation_id": cid})
    assert len(msgs) == 4
    assert all(row.get("turn_id") for row in msgs)
    history = load_history(db, conversation_id=cid, sub="google-1")
    assert [row["role"] for row in history] == ["user", "assistant", "user", "assistant"]
    listed = list_conversations(db, sub="google-1")
    assert listed[0]["id"] == cid
    detail = get_conversation(db, conversation_id=cid, sub="google-1")
    assert len(detail["messages"]) == 4
    summary = summarize_chat_turns(db)
    assert summary["turns"] == 3
    assert summary["conversations"] == 2
    assert summary["users"] == 2
    assert summary["llm_tokens"] == 54
    assert summary["avg_latency_ms"] == 10
    assert [row["key"] for row in summary["by_module"]] == ["khao_khi", "thong_tin_chung"]
    khao = summary["by_module"][0]
    assert khao["n"] == 2
    assert khao["turns"] == 2
    assert khao["conversations"] == 1
    assert khao["users"] == 1
    assert khao["llm_tokens"] == 50
    assert khao["avg_latency_ms"] == 12
    assert khao["by_routing"] == [{"key": "cosine", "n": 1}, {"key": "regex", "n": 1}]
    chung = summary["by_module"][1]
    assert chung["turns"] == 1
    assert chung["by_status"] == [{"key": "out_of_scope", "n": 1}]
    one = summarize_chat_turns(db, module_code="thong_tin_chung")
    assert one["turns"] == 1
    assert one["by_module"] == [chung]
