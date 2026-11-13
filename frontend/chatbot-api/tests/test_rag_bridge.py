from app.services.rag import (
    citations_for_frontend,
    iter_named_sse,
    map_rag_target,
    translate_rag_event,
)


def test_dbcl_module_1_maps_to_khao_khi():
    assert map_rag_target("dbcl", "module_1") == ("bao_dam_chat_luong", "khao_khi")
    assert map_rag_target("dbcl", "module_2") is None
    assert map_rag_target("hc", "module_1") is None
    assert map_rag_target("khcn", "module_1") is None


def test_rag_route_overlay_keeps_dbcl_and_adds_room():
    from app.services.rag import merged_rag_routes

    routes = merged_rag_routes(
        {"pdt": {"department_id": "phong_dao_tao", "modules": {"module_1": "dkhp"}}}
    )
    assert map_rag_target("dbcl", "module_1", routes) == ("bao_dam_chat_luong", "khao_khi")
    assert map_rag_target("pdt", "module_1", routes) == ("phong_dao_tao", "dkhp")


def test_unmapped_department_falls_back_to_stub():
    from app.services.rag import RagAnswerProvider

    class Settings:
        rag_base_url = "http://127.0.0.1:9"
        rag_api_key = "unused"
        rag_timeout_seconds = 2

    events = list(RagAnswerProvider(Settings()).iter_sse("hc", "module_1", "Xin chào"))
    assert events[-1]["type"] == "done"
    assert events[-1]["provider"] == "stub"
    assert "Hành chính" in events[-1]["response"] or "UEL" in events[-1]["response"]


def test_citations_drop_chunk_ids():
    mapped = citations_for_frontend(
        [
            {"kind": "document_code", "value": "TL02"},
            {"kind": "chunk_id", "value": "gold:aaaaaaaaaaaaaaaaaaaaaaaa"},
            {"kind": "question_code", "value": "I.2.012"},
        ]
    )
    assert [item["source"] for item in mapped] == ["TL02", "I.2.012"]
    assert mapped[0]["source_kind"] == "document"
    assert mapped[1]["source_kind"] == "faq"


def test_translate_named_sse_to_fe_contract():
    token = translate_rag_event(
        "token", {"text": "Hạn "}, mode="module_1", user_message="hỏi", conversation_id="c1"
    )
    assert token == {"type": "token", "text": "Hạn "}
    status = translate_rag_event(
        "status",
        {"stage": "generate", "label": "Đang soạn câu trả lời…"},
        mode="module_1",
        user_message="hỏi",
        conversation_id="c1",
    )
    assert status["type"] == "status"
    done = translate_rag_event(
        "done",
        {
            "answer": "Hạn 02 ngày.",
            "citations": [{"kind": "document_code", "value": "TL02"}],
            "support_contact": "Phòng BDCL",
        },
        mode="module_1",
        user_message="hỏi",
        conversation_id="c1",
    )
    assert done["type"] == "done"
    assert done["response"] == "Hạn 02 ngày."
    assert done["conversation_id"] == "c1"
    assert done["citations"][0]["source"] == "TL02"


def test_iter_named_sse_splits_event_blocks():
    chunks = [
        b'event: status\ndata: {"label":"start"}\n\n',
        b'event: token\ndata: {"text":"ab"}\n\n',
        b'event: done\ndata: {"answer":"ab"}\n\n',
    ]
    events = list(iter_named_sse(iter(chunks)))
    assert events[0][0] == "status"
    assert events[1] == ("token", {"text": "ab"})
    assert events[2][1]["answer"] == "ab"
