from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from app.integrations.qdrant import MemoryQdrant
from app.services.ingest_service import ingest_module
from tests.conftest import logged_in_client

GOLD_PATH = Path(__file__).resolve().parent / "gold_chat.yaml"
SEED_DIR = Path(__file__).resolve().parents[2] / "chatbot-data" / "modules" / "khao_khi" / "seed"
PERSONA_PATH = Path(__file__).resolve().parents[1] / "configs" / "persona.yaml"
SEED_FILES = {
    1: "1. Thong tin Mo-dun - Khao khi.xlsx",
    2: "2. FAQ - Khao khi.xlsx",
    3: "3. Tai lieu nghiep vu - Khao khi.xlsx",
    4: "4. Moc thoi gian.xlsx",
    5: "5. Tai lieu gioi thieu.xlsx",
}


def _sse_done(text: str) -> dict:
    for line in text.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            if payload.get("type") == "done":
                return payload
    return {}


def _fold_ws(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _seed_pack() -> dict[int, bytes]:
    missing = [name for name in SEED_FILES.values() if not (SEED_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Thiếu seed Khảo thí: {missing}")
    return {slot: (SEED_DIR / name).read_bytes() for slot, name in SEED_FILES.items()}


def _gold_client(tmp_path: Path):
    client = logged_in_client(email="sv@gmail.com")
    client.app.state.qdrant = MemoryQdrant()
    client.app.state.qdrant_ok = True
    client.app.state.settings.chatbot_data_dir = tmp_path
    client.app.state.settings.embed_backend = "hash"
    client.app.state.settings.llm_api_key = ""
    persona = yaml.safe_load(PERSONA_PATH.read_text(encoding="utf-8")) or {}
    client.app.state.persona = persona
    dept = dict(client.app.state.department or {})
    dept.setdefault("handoff_form_url", "https://docs.google.com/forms/")
    dept["modules"] = [
        {"code": "khao_khi", "name": "Khảo khí", "profile": "generic"},
        {"code": "thong_tin_chung", "name": "Thông tin chung", "profile": "generic"},
    ]
    dept["rate_limit"] = {"chats_per_minute": 1000, "llm_tokens_per_day": 50000}
    client.app.state.department = dept
    return client


def _chat(client, question: str, module_code: str) -> dict:
    res = client.post(
        "/api/chat/stream",
        json={"message": question, "module_code": module_code},
    )
    assert res.status_code == 200, res.text
    return _sse_done(res.text)


def _check_case(done: dict, case: dict) -> list[str]:
    exp = case.get("expect") or {}
    errors: list[str] = []
    source = done.get("routing_source")
    status = done.get("status")
    answer = str(done.get("answer") or "")
    if "routing_source" in exp and source != exp["routing_source"]:
        errors.append(f"routing_source={source} want {exp['routing_source']}")
    if "routing_source_any" in exp and source not in exp["routing_source_any"]:
        errors.append(f"routing_source={source} want one of {exp['routing_source_any']}")
    if "not_routing" in exp and source == exp["not_routing"]:
        errors.append(f"routing_source must not be {exp['not_routing']}")
    if "status" in exp and status != exp["status"]:
        errors.append(f"status={status} want {exp['status']}")
    if "status_any" in exp and status not in exp["status_any"]:
        errors.append(f"status={status} want one of {exp['status_any']}")
    if "answer_equals" in exp and _fold_ws(answer) != _fold_ws(str(exp["answer_equals"])):
        errors.append("answer not nguyên văn FAQ")
    if "answer_contains" in exp and str(exp["answer_contains"]) not in answer:
        errors.append(f"answer missing {exp['answer_contains']!r}")
    if exp.get("form") is True:
        kind = (done.get("interactive") or {}).get("kind")
        if kind != "form":
            errors.append(f"interactive={kind} want form")
    if exp.get("form") is False and done.get("interactive"):
        errors.append("FAQ không được hiện form")
    if exp.get("no_invent"):
        sourced = bool(done.get("citations")) or bool(done.get("rule_id")) or status in {
            "faq_exact",
            "human_handoff",
            "out_of_scope",
            "clarification_required",
        }
        insufficient = "chưa đủ nguồn" in answer.lower() or "không đoán" in answer.lower()
        if status == "answer_allowed" and not sourced and not insufficient:
            errors.append("answer_allowed without source — có thể đoán")
    return errors


def test_persona_regex_compiles() -> None:
    persona = yaml.safe_load(PERSONA_PATH.read_text(encoding="utf-8")) or {}
    for item in persona.get("routing_regex") or []:
        re.compile(item["pattern"])


def test_gold_chat_seed_khao_khi(tmp_path: Path) -> None:
    spec = yaml.safe_load(GOLD_PATH.read_text(encoding="utf-8"))
    cases = spec["cases"]
    meta = spec["meta"]
    assert len(cases) >= int(meta["min_cases"])
    client = _gold_client(tmp_path)
    pack = _seed_pack()
    ingest_module(
        db=client.app.state.db,
        qdrant=client.app.state.qdrant,
        data_dir=tmp_path,
        department=client.app.state.department,
        module_code="khao_khi",
        files=pack,
        filenames={i: name for i, name in SEED_FILES.items()},
        embed_dim=1024,
        embed_backend="hash",
    )
    failed: list[str] = []
    for case in cases:
        module_code = case.get("module_code") or meta["module_code"]
        done = _chat(client, case["question"], module_code)
        errors = _check_case(done, case)
        if errors:
            failed.append(f"{case['id']}: {'; '.join(errors)} | got {done.get('routing_source')}/{done.get('status')}")
    passed = len(cases) - len(failed)
    rate = passed / len(cases)
    report = GOLD_PATH.with_name("gold_chat.last.json")
    report.write_text(
        json.dumps(
            {"passed": passed, "total": len(cases), "rate": round(rate, 4), "failed": failed},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    assert rate >= float(meta["min_pass_rate"]), (
        f"gold {passed}/{len(cases)} = {rate:.0%} < {meta['min_pass_rate']:.0%}\n" + "\n".join(failed)
    )
