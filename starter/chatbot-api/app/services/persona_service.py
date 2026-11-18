from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

PERSONA_DOC_ID = "current"


class RegexRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pattern: str = Field(..., min_length=1, max_length=500)
    rule_id: str = Field(..., min_length=1, max_length=240)


class PersonaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    greeting: str = Field("", max_length=4000)
    out_of_scope: str = Field("", max_length=4000)
    clarification: str = Field("", max_length=4000)
    role: str = Field("", max_length=400)
    constraints: str = Field("", max_length=4000)
    glossary: dict[str, str] = Field(default_factory=dict)
    answer_style: str = Field("", max_length=4000)
    routing_regex: list[RegexRow] = Field(default_factory=list, max_length=50)
    cosine_threshold: float = Field(0.62, ge=0, le=1)
    top_k: int = Field(6, ge=1, le=20)

    @field_validator("glossary")
    @classmethod
    def _glossary_size(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 50:
            raise ValueError("glossary tối đa 50 mục")
        cleaned: dict[str, str] = {}
        for key, val in value.items():
            k = str(key or "").strip()
            if not k:
                continue
            cleaned[k] = str(val or "").strip()
        return cleaned


def public_persona(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = raw or {}
    regex_rows = []
    for row in data.get("routing_regex") or []:
        if not isinstance(row, dict):
            continue
        pattern = str(row.get("pattern") or "").strip()
        rule_id = str(row.get("rule_id") or "").strip()
        if pattern and rule_id:
            regex_rows.append({"pattern": pattern, "rule_id": rule_id})
    glossary = data.get("glossary") or {}
    if not isinstance(glossary, dict):
        glossary = {}
    try:
        threshold = float(data.get("cosine_threshold") if data.get("cosine_threshold") is not None else 0.62)
    except (TypeError, ValueError):
        threshold = 0.62
    try:
        top_k = int(data.get("top_k") if data.get("top_k") is not None else 6)
    except (TypeError, ValueError):
        top_k = 6
    return {
        "greeting": str(data.get("greeting") or ""),
        "out_of_scope": str(data.get("out_of_scope") or ""),
        "clarification": str(data.get("clarification") or ""),
        "role": str(data.get("role") or ""),
        "constraints": str(data.get("constraints") or ""),
        "glossary": {str(k): str(v or "") for k, v in glossary.items()},
        "answer_style": str(data.get("answer_style") or ""),
        "routing_regex": regex_rows,
        "cosine_threshold": max(0.0, min(1.0, threshold)),
        "top_k": max(1, min(20, top_k)),
    }


def runtime_persona(*, db, yaml_data: dict[str, Any] | None) -> dict[str, Any]:
    seed = public_persona(yaml_data)
    stored = load_persona_doc(db)
    if stored:
        return public_persona(stored)
    return seed


def load_persona_doc(db) -> dict[str, Any] | None:
    if db is None:
        return None
    return (
        db["persona"].find_one({"_id": PERSONA_DOC_ID})
        or db["persona"].find_one({"active": True})
        or db["persona"].find_one({})
    )


def active_topics(db, department: dict[str, Any]) -> list[dict[str, str]]:
    if db is None:
        return []
    from app.repositories import catalog

    out: list[dict[str, str]] = []
    for mod in department.get("modules") or []:
        code = mod.get("code")
        if not code:
            continue
        rel = catalog.get_active_release(db, code)
        if not rel:
            continue
        release_id = rel.get("release_id")
        for row in catalog.find_docs(db, "routing_rules", {"module_code": code, "release_id": release_id}):
            out.append(
                {
                    "module_code": str(code),
                    "module_name": str(mod.get("name") or code),
                    "release_id": str(release_id or ""),
                    "rule_id": str(row.get("rule_id") or ""),
                    "topic": str(row.get("topic") or ""),
                    "scope_code": str(row.get("scope_code") or ""),
                }
            )
    return [row for row in out if row["rule_id"]]


def stale_regex(rows: list[dict[str, str]], known_ids: set[str]) -> list[dict[str, Any]]:
    stale = []
    for i, row in enumerate(rows):
        rid = row.get("rule_id") or ""
        if rid and rid not in known_ids:
            stale.append({"index": i, "rule_id": rid, "pattern": row.get("pattern") or "", "topic": ""})
    return stale


def validate_regex(rows: list[RegexRow], known_ids: set[str]) -> list[str]:
    errors: list[str] = []
    if rows and not known_ids:
        errors.append("Chưa có File 01 đang chạy — nạp tri thức trước khi gán regex.")
        return errors
    for i, row in enumerate(rows, start=1):
        try:
            re.compile(row.pattern)
        except re.error as exc:
            errors.append(f"Regex dòng {i}: {exc}")
        if row.rule_id not in known_ids:
            errors.append(f"Regex dòng {i}: chọn lại chủ đề từ File 01 đang chạy (không còn {row.rule_id})")
    return errors


def save_persona(db, *, payload: PersonaIn, email: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = {
        "_id": PERSONA_DOC_ID,
        "active": True,
        "updated_at": now,
        "updated_by": email,
        **payload.model_dump(),
        "routing_regex": [row.model_dump() for row in payload.routing_regex],
    }
    if db is None:
        return public_persona(doc)
    existing = db["persona"].find_one({"_id": PERSONA_DOC_ID})
    if existing is None:
        db["persona"].insert_one(doc)
    else:
        db["persona"].update_one({"_id": PERSONA_DOC_ID}, {"$set": {k: v for k, v in doc.items() if k != "_id"}})
    return public_persona(doc)


def write_audit(db, *, action: str, email: str, meta: dict[str, Any] | None = None) -> None:
    if db is None:
        return
    db["audit"].insert_one(
        {
            "action": action,
            "email": email,
            "at": datetime.now(timezone.utc),
            "meta": meta or {},
        }
    )
