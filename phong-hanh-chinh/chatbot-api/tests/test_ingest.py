from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from app.integrations.qdrant import MemoryQdrant
from app.repositories import catalog
from app.services.ingest_service import recover_missing_releases
from tests.conftest import logged_in_client
from tests.excel_fixtures import (
    SCOPE_HANDOFF,
    fill_file01,
    fill_file02,
    fill_file04,
    valid_pack,
)


def _admin(tmp_path: Path):
    client = logged_in_client(email="boss@uel.edu.vn", admins=["boss@uel.edu.vn"])
    client.app.state.qdrant = MemoryQdrant()
    client.app.state.qdrant_ok = True
    client.app.state.settings.chatbot_data_dir = tmp_path
    src = Path(client.app.state.settings.department_yaml)
    if not src.is_file():
        src = Path(__file__).resolve().parents[1] / "configs" / "department.yaml"
    dest = tmp_path / "department.yaml"
    shutil.copy2(src, dest)
    client.app.state.settings.department_yaml = dest
    return client


def _post_ingest(client, files: dict[int, bytes], module_code: str = "thong_tin_chung"):
    data = {"module_code": module_code}
    upload = {f"file_0{i}": (f"{i}.xlsx", files[i], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") for i in range(1, 6)}
    return client.post("/api/admin/ingest", data=data, files=upload)


def _sse_done(text: str) -> dict:
    for line in text.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            if payload.get("type") == "done":
                return payload
    return {}


def test_missing_file_422(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    files = valid_pack()
    data = {"module_code": "thong_tin_chung"}
    upload = {f"file_0{i}": (f"{i}.xlsx", files[i], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") for i in range(1, 5)}
    res = client.post("/api/admin/ingest", data=data, files=upload)
    assert res.status_code == 422


def test_valid_five_files_empty_04_05(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    res = _post_ingest(client, valid_pack())
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["module_code"] == "thong_tin_chung"
    assert body["counts"]["rules"] >= 1
    assert "File 04" in " ".join(body["warnings"])
    assert "File 05" in " ".join(body["warnings"])
    source = tmp_path / "modules" / "thong_tin_chung" / "releases" / body["release_id"] / "source"
    assert source.is_dir()
    assert len(list(source.glob("*.xlsx"))) == 5
    rules = catalog.find_docs(client.app.state.db, "routing_rules", {"release_id": body["release_id"]})
    assert rules[0]["rule_id"].startswith("thong_tin_chung.")
    chat = client.post("/api/chat/stream", json={"message": "xin chào", "module_code": "thong_tin_chung"})
    assert chat.status_code == 200
    done = _sse_done(chat.text)
    assert done["release_id"] == body["release_id"]
    qdrant = client.app.state.qdrant
    assert any(p["release_id"] == body["release_id"] for p in qdrant.rules)
    rule_pt = next(p for p in qdrant.rules if p["release_id"] == body["release_id"])
    assert rule_pt.get("scope_code") in {"answer_allowed", "human_handoff", "out_of_scope"}
    assert rule_pt.get("rule_id")
    assert rule_pt.get("topic")
    faq_docs = [p for p in qdrant.docs if p.get("source") == "faq" and p.get("release_id") == body["release_id"]]
    assert len(faq_docs) == body["counts"]["faqs"]
    assert faq_docs[0]["retrieve_boost"] == 1.5
    qa = client.get("/api/qa")
    assert qa.status_code == 200
    listed = qa.json()
    assert len(listed) == body["counts"]["faqs"]
    assert listed[0]["question"]
    assert listed[0]["answer"]
    assert "section" in listed[0]
    modes = client.get("/api/chat/modes")
    assert modes.status_code == 200
    labels = {m["id"]: m for m in modes.json()["modes"]}
    assert labels["module_2"]["description"]
    this_mod = client.get("/api/qa", params={"mode": "module_2"})
    assert this_mod.status_code == 200
    assert len(this_mod.json()) == body["counts"]["faqs"]
    other = client.get("/api/qa", params={"mode": "module_1"})
    assert other.status_code == 200
    assert other.json() == []


def test_bad_scope_keeps_old_release(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    first = _post_ingest(client, valid_pack())
    assert first.status_code == 200
    old_id = first.json()["release_id"]
    bad = valid_pack()
    bad[1] = fill_file01(scope="Không phải scope")
    second = _post_ingest(client, bad)
    assert second.status_code == 422
    assert any("scope" in e.lower() for e in second.json()["detail"]["errors"])
    active = catalog.get_active_release(client.app.state.db, "thong_tin_chung")
    assert active["release_id"] == old_id


def test_duplicate_faq_422(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    pack = valid_pack()
    pack[2] = fill_file02(duplicate_question=True)
    res = _post_ingest(client, pack)
    assert res.status_code == 422
    assert any("chuẩn hóa" in e.lower() or "trùng" in e.lower() for e in res.json()["detail"]["errors"])


def test_duplicate_topic_slug_422(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    pack = valid_pack()
    pack[1] = fill_file01(extra_topics=[("Hạn phúc khảo", SCOPE_HANDOFF)])
    res = _post_ingest(client, pack)
    assert res.status_code == 422
    assert any("slug" in e.lower() for e in res.json()["detail"]["errors"])


def test_khao_khi_pack_ingests(tmp_path: Path) -> None:
    folder = Path(__file__).resolve().parents[2] / "chatbot-data" / "modules" / "khao_khi" / "seed"
    files = {}
    for path in folder.glob("*.xlsx"):
        match = re.search(r"(\d+)\.", path.name)
        if match:
            files[int(match.group(1))] = path.read_bytes()
    assert set(files) == {1, 2, 3, 4, 5}
    client = _admin(tmp_path)
    res = _post_ingest(client, files, module_code="khao_khi")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["counts"]["rules"] >= 1
    assert body["counts"]["faqs"] >= 1
    qdrant = client.app.state.qdrant
    assert len(qdrant.rules) == body["counts"]["rules"]
    assert len(qdrant.docs) == body["counts"]["docs"]


def test_member_cannot_ingest(tmp_path: Path) -> None:
    from tests.conftest import logged_in_client as login

    client = login(email="sv@gmail.com")
    client.app.state.qdrant = MemoryQdrant()
    client.app.state.settings.chatbot_data_dir = tmp_path
    res = _post_ingest(client, valid_pack())
    assert res.status_code == 403


def test_composite_audience_maps_and_ingests(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    pack = valid_pack(
        primary_audience="Sinh viên đại học (chính quy, vừa làm vừa học, từ xa)",
        audience="Sinh viên đại học (chính quy, vừa làm vừa học, từ xa)",
    )
    res = _post_ingest(client, pack)
    assert res.status_code == 200, res.text
    body = res.json()
    joined = " ".join(body["warnings"])
    assert "chuẩn hóa" in joined
    assert "Sinh viên (mọi hệ)" in joined
    rules = catalog.find_docs(client.app.state.db, "routing_rules", {"module_code": "thong_tin_chung"})
    assert rules[0]["audience"] == "Sinh viên (mọi hệ)"
    issues = body.get("issues") or []
    assert any(item.get("mapped") == "Sinh viên (mọi hệ)" for item in issues)


def test_file04_missing_dates_are_warnings(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    pack = valid_pack()
    pack[4] = fill_file04(
        [
            {
                "milestone_id": "M003",
                "name": "Ngày chốt dữ liệu xét chuẩn đầu ra ngoại ngữ",
                "kind": "Hạn chót",
                "full_text": "Chốt dữ liệu xét chuẩn đầu ra ngoại ngữ.",
            },
            {
                "milestone_id": "M005",
                "name": "Công bố kết quả và quyết định công nhận đạt chuẩn",
                "kind": "Sự kiện",
                "full_text": "Công bố kết quả ngày 15/06/2026.",
            },
            {
                "milestone_id": "M015",
                "name": "Lễ tốt nghiệp năm học 2026-2027",
                "kind": "Sự kiện",
                "full_text": "Lễ tốt nghiệp năm học 2026-2027.",
            },
        ]
    )
    res = _post_ingest(client, pack)
    assert res.status_code == 200, res.text
    body = res.json()
    joined = " ".join(body["warnings"])
    assert "M003" in joined
    assert "M015" in joined
    assert body["counts"]["milestones"] == 3
    rows = catalog.find_docs(client.app.state.db, "milestones", {"module_code": "thong_tin_chung"})
    by_id = {row["milestone_id"]: row for row in rows}
    assert by_id["M005"]["start"] == "2026-06-15"
    assert not (by_id["M003"].get("start") or by_id["M003"].get("end"))


def test_ingest_check_lists_choices_without_writing(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    files = valid_pack(scope="Không phải scope")
    data = {"module_code": "thong_tin_chung"}
    upload = {
        f"file_0{i}": (f"{i}.xlsx", files[i], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        for i in range(1, 6)
    }
    res = client.post("/api/admin/ingest/check", data=data, files=upload)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is False
    assert any("scope" in e.lower() for e in body["errors"])
    assert "Sinh viên (mọi hệ)" in body["choices"]["audience"]
    assert catalog.get_active_release(client.app.state.db, "thong_tin_chung") is None


def test_ingest_stream_emits_progress(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    files = valid_pack()
    data = {"module_code": "thong_tin_chung"}
    upload = {
        f"file_0{i}": (f"{i}.xlsx", files[i], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        for i in range(1, 6)
    }
    res = client.post("/api/admin/ingest/stream", data=data, files=upload)
    assert res.status_code == 200, res.text
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    types = [ev.get("type") for ev in events]
    assert "progress" in types
    assert types[-1] == "done"
    assert events[-1]["counts"]["rules"] >= 1
    assert events[-1]["module_code"] == "thong_tin_chung"


def test_email_in_channel_column_is_warning_not_error(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    pack = valid_pack(channel="phongdaotao@uel.edu.vn")
    res = _post_ingest(client, pack)
    assert res.status_code == 200, res.text
    joined = " ".join(res.json()["warnings"])
    assert "Kênh" in joined
    rules = catalog.find_docs(client.app.state.db, "routing_rules", {"module_code": "thong_tin_chung"})
    assert "phongdaotao@uel.edu.vn" in (rules[0].get("contact_info") or "")
    assert not (rules[0].get("channel") or "")


def test_recover_missing_release_from_disk(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    pack = valid_pack()
    source = tmp_path / "modules" / "thong_tin_chung" / "releases" / "r-old" / "source"
    source.mkdir(parents=True)
    for idx, blob in pack.items():
        (source / f"{idx}.xlsx").write_bytes(blob)
    recovered = recover_missing_releases(
        db=client.app.state.db,
        qdrant=client.app.state.qdrant,
        data_dir=tmp_path,
        department=client.app.state.department,
        embed_dim=1024,
        embed_backend="hash",
    )
    assert recovered and recovered[0]["module_code"] == "thong_tin_chung"
    assert recovered[0]["counts"]["faqs"] >= 1
    chat = client.post(
        "/api/chat/stream",
        json={"message": "Hạn phúc khảo ĐHCQ là bao lâu?", "module_code": "thong_tin_chung"},
    )
    assert chat.status_code == 200, chat.text
    done = _sse_done(chat.text)
    assert done["routing_source"] == "faq_exact"
    again = recover_missing_releases(
        db=client.app.state.db,
        qdrant=client.app.state.qdrant,
        data_dir=tmp_path,
        department=client.app.state.department,
        embed_dim=1024,
        embed_backend="hash",
    )
    assert again == []


def test_recover_skips_empty_latest_release(tmp_path: Path) -> None:
    client = _admin(tmp_path)
    pack = valid_pack()
    good = tmp_path / "modules" / "thong_tin_chung" / "releases" / "r-old" / "source"
    good.mkdir(parents=True)
    for idx, blob in pack.items():
        (good / f"{idx}.xlsx").write_bytes(blob)
    empty = tmp_path / "modules" / "thong_tin_chung" / "releases" / "z-newer-empty" / "source"
    empty.mkdir(parents=True)
    for idx in range(1, 6):
        (empty / f"{idx}.xlsx").write_bytes(b"")
    recovered = recover_missing_releases(
        db=client.app.state.db,
        qdrant=client.app.state.qdrant,
        data_dir=tmp_path,
        department=client.app.state.department,
        embed_dim=1024,
        embed_backend="hash",
    )
    assert recovered and recovered[0]["module_code"] == "thong_tin_chung"
    assert recovered[0]["counts"]["faqs"] >= 1
