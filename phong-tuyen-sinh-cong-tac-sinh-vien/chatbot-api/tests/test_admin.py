from __future__ import annotations

from pathlib import Path

from tests.conftest import logged_in_client
from tests.excel_fixtures import valid_pack
from tests.test_ingest import _admin, _post_ingest, _sse_done

PERSONA = {
    "greeting": "Xin chào P5",
    "out_of_scope": "Ngoài phạm vi P5",
    "clarification": "XYZ_P5_CLARIFY",
    "role": "Trợ lý test",
    "constraints": "Không bịa",
    "glossary": {"phúc khảo": "xem lại điểm"},
    "answer_style": "Ngắn",
    "routing_regex": [],
    "cosine_threshold": 0.62,
    "top_k": 6,
}


def test_member_cannot_get_or_put_persona() -> None:
    client = logged_in_client(email="sv@gmail.com", admins=["boss@uel.edu.vn"])
    assert client.get("/api/admin/persona").status_code == 403
    assert client.put("/api/admin/persona", json=PERSONA).status_code == 403
    assert client.get("/api/admin/topics").status_code == 403


def test_admin_get_persona_from_yaml() -> None:
    client = logged_in_client(email="boss@uel.edu.vn", admins=["boss@uel.edu.vn"])
    res = client.get("/api/admin/persona")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["source"] == "yaml"
    assert "greeting" in body["persona"]
    assert body["persona"]["cosine_threshold"] == 0.62
    status = client.get("/api/admin/status")
    assert status.json()["persona"] == "ready"
    assert status.json()["modules"]


def test_put_rejects_system_prompt() -> None:
    client = logged_in_client(email="boss@uel.edu.vn", admins=["boss@uel.edu.vn"])
    res = client.put("/api/admin/persona", json={**PERSONA, "system_prompt": "bỏ an toàn"})
    assert res.status_code == 422


def test_put_rejects_unknown_rule_id() -> None:
    client = logged_in_client(email="boss@uel.edu.vn", admins=["boss@uel.edu.vn"])
    res = client.put(
        "/api/admin/persona",
        json={
            **PERSONA,
            "routing_regex": [{"pattern": "(?i)phúc khảo", "rule_id": "thong_tin_chung.khong-ton-tai"}],
        },
    )
    assert res.status_code == 422
    assert "File 01" in str(res.json()["detail"])


def test_put_persona_applies_to_trial_chat(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    ingested = _post_ingest(client, valid_pack())
    assert ingested.status_code == 200, ingested.text
    res = client.put("/api/admin/persona", json=PERSONA)
    assert res.status_code == 200, res.text
    assert res.json()["source"] == "mongo"
    got = client.get("/api/admin/persona")
    assert got.json()["persona"]["clarification"] == "XYZ_P5_CLARIFY"
    chat = client.post(
        "/api/chat/stream",
        json={"message": "xyzabc câu lạ không faq", "module_code": "thong_tin_chung", "trial": True},
    )
    assert chat.status_code == 200
    done = _sse_done(chat.text)
    assert "XYZ_P5_CLARIFY" in done["answer"]
    assert done["routing_source"] == "llm_clarify"


def test_regex_dropdown_from_active_file01(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    ingested = _post_ingest(client, valid_pack())
    assert ingested.status_code == 200, ingested.text
    body = ingested.json()
    assert body["checksums"]
    assert len(body["files"]) == 5
    assert "file03_sheets" in body["counts"]
    topics = client.get("/api/admin/topics", params={"module_code": "thong_tin_chung"})
    assert topics.status_code == 200
    rows = topics.json()["topics"]
    assert rows
    rule_id = rows[0]["rule_id"]
    assert rows[0]["topic"]
    saved = client.put(
        "/api/admin/persona",
        json={
            **PERSONA,
            "routing_regex": [{"pattern": "(?i)hạn phúc khảo p5", "rule_id": rule_id}],
        },
    )
    assert saved.status_code == 200, saved.text
    chat = client.post(
        "/api/chat/stream",
        json={"message": "hạn phúc khảo p5", "module_code": "thong_tin_chung", "trial": True},
    )
    assert chat.status_code == 200
    done = _sse_done(chat.text)
    assert done["routing_source"] == "regex"
    assert done["rule_id"] == rule_id


def test_member_cannot_add_module() -> None:
    client = logged_in_client(email="sv@gmail.com", admins=["boss@uel.edu.vn"])
    assert client.post("/api/admin/modules", json={"name": "Học phí thử"}).status_code == 403


def test_add_module_then_ingest(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    created = client.post("/api/admin/modules", json={"name": "Học phí thử"})
    assert created.status_code == 200, created.text
    assert created.json()["module"]["code"] == "hoc_phi_thu"
    folder = tmp_path / "modules" / "hoc_phi_thu"
    assert folder.is_dir()
    assert (folder / "module.yaml").is_file()
    yaml_text = (tmp_path / "department.yaml").read_text(encoding="utf-8")
    assert "hoc_phi_thu" in yaml_text
    assert "Học phí thử" in yaml_text
    modules_yaml = (tmp_path / "modules.yaml").read_text(encoding="utf-8")
    assert "hoc_phi_thu" in modules_yaml
    assert created.json()["module"]["yaml"]
    dup = client.post("/api/admin/modules", json={"name": "Học phí thử"})
    assert dup.status_code == 422
    codes = [m["code"] for m in client.get("/api/admin/status").json()["modules"]]
    assert "hoc_phi_thu" in codes
    pack = valid_pack(module_name="Học phí thử")
    res = _post_ingest(client, pack, module_code="hoc_phi_thu")
    assert res.status_code == 200, res.text
    assert res.json()["module_code"] == "hoc_phi_thu"
