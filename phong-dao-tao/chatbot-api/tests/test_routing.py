from __future__ import annotations

import json
from pathlib import Path

from app.ingestion.excel import SCOPE_ANSWER, SCOPE_HANDOFF, SCOPE_OOS
from app.ingestion.normalize import slug
from app.integrations.embeddings import hash_embed
from app.integrations.qdrant import MemoryQdrant
from app.repositories import catalog
from app.services.ingest_service import ingest_module
from app.services.llm import parse_rule_id
from app.services.rag import retrieve_docs
from app.services.routing import NO_DATA_ANSWER, compose_search_query
from tests.conftest import logged_in_client
from tests.excel_fixtures import fill_file03, valid_pack
from tests.test_ingest import _sse_done


FAQ_Q = "Hạn phúc khảo ĐHCQ là bao lâu?"
FAQ_A = "02 ngày làm việc kể từ ngày công bố điểm."
HANDOFF_TOPIC = "Chuyển cán bộ phúc khảo"
OOS_TOPIC = "Học phí ngoài phạm vi"


def _client(tmp_path: Path, *, form_url: str = "https://forms.gle/p4-test"):
    client = logged_in_client(email="sv@gmail.com")
    client.app.state.qdrant = MemoryQdrant()
    client.app.state.qdrant_ok = True
    client.app.state.settings.chatbot_data_dir = tmp_path
    client.app.state.settings.embed_backend = "hash"
    client.app.state.settings.llm_api_key = ""
    dept = dict(client.app.state.department or {})
    dept["handoff_form_url"] = form_url
    dept["modules"] = [{"code": "thong_tin_chung", "name": "Thông tin chung", "profile": "generic"}]
    client.app.state.department = dept
    client.app.state.persona = {
        "clarification": "Bạn đang hỏi điều gì?",
        "out_of_scope": "Câu này ngoài phạm vi.",
        "routing_regex": [],
        "cosine_threshold": 0.62,
        "top_k": 6,
        "role": "Trợ lý test",
        "constraints": "Không bịa.",
        "answer_style": "Ngắn.",
    }
    return client


def _ingest(client, tmp_path: Path, pack=None, module_code: str = "thong_tin_chung"):
    files = pack or valid_pack()
    return ingest_module(
        db=client.app.state.db,
        qdrant=client.app.state.qdrant,
        data_dir=tmp_path,
        department=client.app.state.department,
        module_code=module_code,
        files=files,
        filenames={i: f"{i}.xlsx" for i in files},
        embed_dim=1024,
        embed_backend="hash",
    )


def _chat(client, message: str, **extra) -> dict:
    body = {"message": message, "module_code": "thong_tin_chung"}
    body.update(extra)
    res = client.post("/api/chat/stream", json=body)
    assert res.status_code == 200, res.text
    return _sse_done(res.text)


def _rule_id(topic: str, module_code: str = "thong_tin_chung") -> str:
    return f"{module_code}.{slug(topic)}"


def test_parse_rule_id() -> None:
    allowed = {"thong_tin_chung.han-phuc-khao"}
    assert parse_rule_id('{"rule_id":"thong_tin_chung.han-phuc-khao"}', allowed) == "thong_tin_chung.han-phuc-khao"
    assert parse_rule_id('{"rule_id": null}', allowed) is None
    assert parse_rule_id("thong_tin_chung.khong-co", allowed) is None


def test_missing_release_is_no_data_not_persona_clarify(tmp_path: Path) -> None:
    client = _client(tmp_path)
    done = _chat(client, "chuẩn đầu ra ngoại ngữ là gì")
    assert done["routing_source"] == "no_data"
    assert done["answer"] == NO_DATA_ANSWER
    assert "phúc khảo" not in done["answer"].lower()
    assert "hỏi điều gì" not in done["answer"].lower()


def test_faq_exact_no_llm(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _ingest(client, tmp_path)
    done = _chat(client, FAQ_Q)
    assert done["routing_source"] == "faq_exact"
    assert done["answer"] == FAQ_A
    assert done["status"] == "faq_exact"


def test_regex_handoff_shows_form(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pack = valid_pack(extra_topics=[(HANDOFF_TOPIC, SCOPE_HANDOFF)])
    body = _ingest(client, tmp_path, pack)
    rid = _rule_id(HANDOFF_TOPIC)
    client.app.state.persona["routing_regex"] = [{"pattern": r"(?i)cần cán bộ gấp", "rule_id": rid}]
    done = _chat(client, "Tôi cần cán bộ gấp")
    assert done["routing_source"] == "regex"
    assert done["status"] == "human_handoff"
    assert done["rule_id"] == rid
    assert done["interactive"]["kind"] == "form"
    assert done["interactive"]["url"].startswith("https://forms.gle/")
    assert done["contact_info"]["email"] == "phongbdcl@uel.edu.vn"
    assert body["release_id"] == done["release_id"]
    assert "thu thập biến" not in done["answer"].lower()
    assert "đầu mối" in done["answer"].lower() or "cán bộ" in done["answer"].lower()


def test_compose_query_only_on_followup() -> None:
    hist = [{"role": "user", "content": "Nghiên cứu khoa học có bắt buộc để xét tốt nghiệp không?"}]
    assert compose_search_query("đầu ra tiếng anh là bao nhiêu", hist) == "đầu ra tiếng anh là bao nhiêu"
    composed = compose_search_query("hệ chính quy thì sao", hist)
    assert "Nghiên cứu khoa học" in composed
    assert "hệ chính quy thì sao" in composed


def test_general_question_does_not_cosine_handoff(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pack = valid_pack(extra_topics=[(HANDOFF_TOPIC, SCOPE_HANDOFF)])
    _ingest(client, tmp_path, pack)
    query = "đầu ra tiếng anh là bao nhiêu"
    vec = hash_embed([query])[0]
    for point in client.app.state.qdrant.rules:
        if point.get("scope_code") == "human_handoff":
            point["vector"] = vec
    done = _chat(client, query)
    assert done["status"] != "human_handoff"
    assert done["routing_source"] != "cosine" or done["status"] == "answer_allowed"


def test_personal_case_cosine_still_handoff(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pack = valid_pack(extra_topics=[(HANDOFF_TOPIC, SCOPE_HANDOFF)])
    _ingest(client, tmp_path, pack)
    query = "vướng mắc hồ sơ chứng chỉ của tôi"
    vec = hash_embed([query])[0]
    for point in client.app.state.qdrant.rules:
        if point.get("scope_code") == "human_handoff":
            point["vector"] = vec
    done = _chat(client, query)
    assert done["status"] == "human_handoff"
    assert done["routing_source"] == "cosine"


def test_contact_question_does_not_dump_bot_behavior(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pack = valid_pack(extra_topics=[(HANDOFF_TOPIC, SCOPE_HANDOFF)])
    _ingest(client, tmp_path, pack)
    done = _chat(client, "liên hệ như nào")
    assert done["status"] == "human_handoff"
    assert done["interactive"]["kind"] == "form"
    assert "thu thập biến" not in done["answer"].lower()
    assert "không tự kết luận" not in done["answer"].lower()
    assert "form" in done["answer"].lower() or "đầu mối" in done["answer"].lower() or "cán bộ" in done["answer"].lower()


def test_oos_uses_persona_and_form(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pack = valid_pack(extra_topics=[(OOS_TOPIC, SCOPE_OOS)])
    _ingest(client, tmp_path, pack)
    rid = _rule_id(OOS_TOPIC)
    client.app.state.persona["routing_regex"] = [{"pattern": r"(?i)học phí ngoài", "rule_id": rid}]
    done = _chat(client, "học phí ngoài")
    assert done["routing_source"] == "regex"
    assert done["status"] == "out_of_scope"
    assert "ngoài phạm vi" in done["answer"].lower()
    assert done["interactive"]["kind"] == "form"


def test_cosine_picks_rule(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _ingest(client, tmp_path)
    query = "cau cosine rieng xyz"
    vec = hash_embed([query])[0]
    rules = client.app.state.qdrant.rules
    assert rules
    rules[0]["vector"] = vec
    done = _chat(client, query)
    assert done["routing_source"] == "cosine"
    assert done["rule_id"] == rules[0]["rule_id"]
    assert done["status"] == "answer_allowed"
    assert done["answer"]


def test_cosine_tie_goes_clarify(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pack = valid_pack(extra_topics=[(HANDOFF_TOPIC, SCOPE_HANDOFF), ("Chủ đề khác", SCOPE_ANSWER)])
    _ingest(client, tmp_path, pack)
    query = "cung vector hoa"
    vec = hash_embed([query])[0]
    for point in client.app.state.qdrant.rules:
        point["vector"] = vec
    done = _chat(client, query)
    assert done["routing_source"] == "llm_clarify"
    assert done["status"] == "clarification_required"
    assert "hỏi điều gì" in done["answer"]


def test_llm_picks_rule(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path)
    pack = valid_pack(extra_topics=[(HANDOFF_TOPIC, SCOPE_HANDOFF)])
    _ingest(client, tmp_path, pack)
    rid = _rule_id(HANDOFF_TOPIC)
    client.app.state.settings.llm_api_key = "sk-test"
    client.app.state.persona["cosine_threshold"] = 0.99

    def fake_complete(**kwargs):
        return json.dumps({"rule_id": rid}), 11

    monkeypatch.setattr("app.services.llm.chat_complete", fake_complete)
    done = _chat(client, "xyz vướng mắc hồ sơ phúc khảo của tôi")
    assert done["routing_source"] == "llm"
    assert done["rule_id"] == rid
    assert done["status"] == "human_handoff"
    me = client.get("/api/auth/me").json()
    used = catalog.find_docs(client.app.state.db, "token_daily", {"sub": me["sub"]})
    assert used and used[0]["tokens"] == 11


def test_embed_error_falls_back_to_clarify(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path)
    _ingest(client, tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("embed down")

    monkeypatch.setattr("app.services.routing.embed_texts", boom)
    done = _chat(client, "xyz khong khop faq regex")
    assert done["routing_source"] == "llm_clarify"
    assert done["status"] == "clarification_required"


def test_llm_null_clarifies_no_rag(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path)
    _ingest(client, tmp_path)
    client.app.state.settings.llm_api_key = "sk-test"
    client.app.state.persona["cosine_threshold"] = 0.99
    monkeypatch.setattr("app.services.llm.chat_complete", lambda **kwargs: ('{"rule_id": null}', 4))
    done = _chat(client, "xyz khong khop")
    assert done["routing_source"] == "llm_clarify"
    assert done["status"] == "clarification_required"
    assert done.get("citations") in (None, [])


def test_mode_maps_to_first_module(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _ingest(client, tmp_path)
    done = _chat(client, FAQ_Q, mode="module_1", module_code=None)
    assert done["routing_source"] == "faq_exact"
    assert done["module_code"] == "thong_tin_chung"


def test_hydrate_adds_procedure_chunks(tmp_path: Path) -> None:
    qdrant = MemoryQdrant()
    qdrant.upsert(
        "docs",
        [
            {
                "id": "s1",
                "vector": hash_embed(["dang nhap portal"])[0],
                "module_code": "thong_tin_chung",
                "release_id": "r1",
                "source": "business",
                "sheet": "Tài liệu 1",
                "kind": "step",
                "doc_type_code": "procedure",
                "title": "Quy trình phúc khảo",
                "text": "Đăng nhập Portal UEL",
            },
            {
                "id": "d1",
                "vector": hash_embed(["ho so don"])[0],
                "module_code": "thong_tin_chung",
                "release_id": "r1",
                "source": "business",
                "sheet": "Tài liệu 1",
                "kind": "dossier",
                "doc_type_code": "procedure",
                "title": "Quy trình phúc khảo",
                "text": "Đơn đăng ký phúc khảo",
            },
            {
                "id": "m1",
                "vector": hash_embed(["ket qua portal"])[0],
                "module_code": "thong_tin_chung",
                "release_id": "r1",
                "source": "business",
                "sheet": "Tài liệu 1",
                "kind": "procedure_meta",
                "doc_type_code": "procedure",
                "title": "Quy trình phúc khảo",
                "text": "Kết quả phúc khảo trên Portal",
            },
            {
                "id": "other",
                "vector": hash_embed(["sheet khac"])[0],
                "module_code": "thong_tin_chung",
                "release_id": "r1",
                "source": "business",
                "sheet": "Tài liệu 2",
                "kind": "step",
                "doc_type_code": "procedure",
                "title": "Khác",
                "text": "Bước sheet khác",
            },
        ],
    )
    hits = retrieve_docs(
        qdrant,
        vector=hash_embed(["dang nhap portal"])[0],
        module_code="thong_tin_chung",
        release_id="r1",
        query="các bước phúc khảo",
        top_k=1,
    )
    kinds = {h["kind"] for h in hits}
    sheets = {h["sheet"] for h in hits}
    assert "step" in kinds and "dossier" in kinds and "procedure_meta" in kinds
    assert sheets == {"Tài liệu 1"}


def test_procedure_pack_ingests_steps(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pack = valid_pack()
    pack[3] = fill_file03(procedure=True)
    body = _ingest(client, tmp_path, pack)
    steps = [p for p in client.app.state.qdrant.docs if p.get("kind") == "step"]
    assert steps
    assert body["counts"]["docs"] >= 1


def test_strip_source_marks() -> None:
    from app.services.rag import strip_source_marks

    raw = "ĐHCQ: 02 ngày làm việc.\n\nNguồn: [1], [3], [5]"
    assert "Nguồn" not in strip_source_marks(raw)
    assert "[1]" not in strip_source_marks(raw)
    assert "02 ngày" in strip_source_marks(raw)


def test_generate_answer_asks_for_markdown(monkeypatch) -> None:
    from app.services.rag import generate_answer

    captured: dict = {}

    def fake(**kwargs):
        captured["kwargs"] = kwargs
        captured["messages"] = kwargs["messages"]
        return "**ĐHCQ:** 02 ngày làm việc.", 4

    monkeypatch.setattr("app.services.llm.chat_complete", fake)
    text, tokens = generate_answer(
        query="hạn phúc khảo",
        hits=[{"text": "ĐHCQ 02 ngày làm việc."}],
        persona={"role": "Trợ lý", "constraints": "", "answer_style": ""},
        llm_opts={"api_key": "sk-test", "model": "m", "base_url": "http://x", "provider": "openai"},
    )
    sysmsg = captured["messages"][0]["content"]
    assert "Markdown" in sysmsg
    assert "bảng" in sysmsg.lower()
    assert "[1]" in sysmsg
    assert captured["kwargs"]["max_tokens"] >= 2048
    assert captured["kwargs"]["continue_on_limit"] is True
    assert text.startswith("**ĐHCQ:**")
    assert tokens == 4


def test_looks_cut_off_trailing_comma() -> None:
    from app.services.rag import looks_cut_off

    assert looks_cut_off("Khóa 23 (CTĐT bằng tiếng Việt)\nYêu cầu thấp hơn,")
    assert not looks_cut_off("**ĐHCQ:** 02 ngày làm việc.")


def test_generate_answer_continues_when_cut_off(monkeypatch) -> None:
    from app.services.rag import generate_answer

    calls: list[str] = []

    def fake(**kwargs):
        n = len(calls)
        if n == 0:
            calls.append("cut")
            return "Khóa 23 (CTĐT bằng tiếng Việt)\nYêu cầu thấp hơn,", 20
        calls.append("more")
        return "CEFR B1, IELTS 5.0.", 8

    monkeypatch.setattr("app.services.llm.chat_complete", fake)
    text, tokens = generate_answer(
        query="đầu ra tiếng anh",
        hits=[{"text": "Khóa 23 tiếng Việt CEFR B1."}],
        persona={"role": "Trợ lý"},
        llm_opts={"api_key": "sk-test", "model": "m", "base_url": "http://x", "provider": "openai"},
    )
    assert calls == ["cut", "more"]
    assert "Yêu cầu thấp hơn" in text
    assert "IELTS 5.0" in text
    assert tokens == 28


def test_followup_reuses_rule_and_saves_history(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _ingest(client, tmp_path)
    rid = _rule_id("Hạn phúc khảo")
    client.app.state.persona["routing_regex"] = [{"pattern": r"(?i)phúc khảo", "rule_id": rid}]
    first = _chat(client, "Thời hạn phúc khảo ĐHCQ là bao lâu?")
    assert first["routing_source"] == "regex"
    assert first["conversation_id"]
    second = _chat(client, "hệ chính quy thì sao", conversation_id=first["conversation_id"])
    assert second["routing_source"] != "llm_clarify"
    assert second["status"] == "answer_allowed"
    assert second["rule_id"] == rid
    assert second["conversation_id"] == first["conversation_id"]
    listed = client.get("/api/conversations")
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.json()["conversations"]]
    assert first["conversation_id"] in ids
    detail = client.get(f"/api/conversations/{first['conversation_id']}")
    assert detail.status_code == 200
    roles = [m["role"] for m in detail.json()["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_current_regex_beats_followup_history(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pack = valid_pack(extra_topics=[(OOS_TOPIC, SCOPE_OOS)])
    _ingest(client, tmp_path, pack)
    pk = _rule_id("Hạn phúc khảo")
    oos = _rule_id(OOS_TOPIC)
    client.app.state.persona["routing_regex"] = [
        {"pattern": r"(?i)phúc khảo", "rule_id": pk},
        {"pattern": r"(?i)học phí", "rule_id": oos},
    ]
    first = _chat(client, "Thời hạn phúc khảo ĐHCQ là bao lâu?")
    done = _chat(client, "học phí học kỳ này", conversation_id=first["conversation_id"])
    assert done["routing_source"] == "regex"
    assert done["status"] == "out_of_scope"
