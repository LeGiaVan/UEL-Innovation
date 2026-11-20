from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

HISTORY_LIMIT = 10


def load_history(db, *, conversation_id: str | None, sub: str, limit: int = HISTORY_LIMIT) -> list[dict[str, Any]]:
    if db is None or not conversation_id or not sub:
        return []
    conv = db["conversations"].find_one({"id": conversation_id, "sub": sub})
    if not conv:
        return []
    rows = db["messages"].find({"conversation_id": conversation_id})
    rows = sorted(rows, key=lambda r: r.get("created_at") or datetime.min.replace(tzinfo=timezone.utc))
    return [
        {
            "role": row.get("role") or "user",
            "content": str(row.get("content") or ""),
            "routing_source": row.get("routing_source"),
            "status": row.get("status"),
            "rule_id": row.get("rule_id"),
        }
        for row in rows[-limit:]
        if row.get("content")
    ]


def save_turn(
    db,
    *,
    sub: str,
    conversation_id: str | None,
    module_code: str | None,
    user_message: str,
    answer: str,
    routing_source: str | None = None,
    status: str | None = None,
    rule_id: str | None = None,
    citations: list | None = None,
    contact_info: dict | None = None,
    interactive: dict | None = None,
    department_id: str | None = None,
    release_id: str | None = None,
    llm_tokens: int = 0,
    latency_ms: int | None = None,
    trial: bool = False,
    user_agent: str | None = None,
    email: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    cid = (conversation_id or "").strip()
    owned = db["conversations"].find_one({"id": cid, "sub": sub}) if cid else None
    if owned is None:
        cid = uuid4().hex
        db["conversations"].insert_one(
            {
                "id": cid,
                "sub": sub,
                "email": email,
                "department_id": department_id,
                "module_code": module_code,
                "preview": (user_message or "")[:100],
                "turn_count": 0,
                "created_at": now,
                "updated_at": now,
            }
        )
    turn_index = int(db["chat_turns"].count_documents({"conversation_id": cid}) or 0) + 1
    turn_id = uuid4().hex
    cites = citations or []
    ua = (user_agent or "").strip()[:200] or None
    tokens = int(llm_tokens or 0)
    db["messages"].insert_one(
        {
            "conversation_id": cid,
            "turn_id": turn_id,
            "turn_index": turn_index,
            "sub": sub,
            "department_id": department_id,
            "module_code": module_code,
            "role": "user",
            "content": user_message,
            "created_at": now,
        }
    )
    db["messages"].insert_one(
        {
            "conversation_id": cid,
            "turn_id": turn_id,
            "turn_index": turn_index,
            "sub": sub,
            "department_id": department_id,
            "module_code": module_code,
            "role": "assistant",
            "content": answer,
            "routing_source": routing_source,
            "status": status,
            "rule_id": rule_id,
            "citations": cites,
            "contact_info": contact_info,
            "interactive": interactive,
            "release_id": release_id,
            "llm_tokens": tokens,
            "latency_ms": latency_ms,
            "trial": bool(trial),
            "created_at": now,
        }
    )
    db["chat_turns"].insert_one(
        {
            "id": turn_id,
            "conversation_id": cid,
            "turn_index": turn_index,
            "sub": sub,
            "email": email,
            "department_id": department_id,
            "module_code": module_code,
            "release_id": release_id,
            "user_message": user_message,
            "assistant_answer": answer,
            "routing_source": routing_source,
            "status": status,
            "rule_id": rule_id,
            "citation_count": len(cites),
            "citations": cites,
            "llm_tokens": tokens,
            "latency_ms": latency_ms,
            "trial": bool(trial),
            "user_agent": ua,
            "created_at": now,
        }
    )
    db["conversations"].update_one(
        {"id": cid, "sub": sub},
        {
            "$set": {
                "updated_at": now,
                "module_code": module_code,
                "department_id": department_id,
                "email": email,
                "preview": (user_message or "")[:100],
                "last_status": status,
                "last_routing_source": routing_source,
            },
            "$inc": {"turn_count": 1},
        },
    )
    return cid


def list_conversations(db, *, sub: str, limit: int = 30) -> list[dict[str, Any]]:
    if db is None or not sub:
        return []
    rows = db["conversations"].find({"sub": sub})
    rows = sorted(rows, key=lambda r: r.get("updated_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    out = []
    for row in rows[:limit]:
        updated = row.get("updated_at")
        out.append(
            {
                "id": row.get("id"),
                "preview": row.get("preview") or "",
                "module_code": row.get("module_code"),
                "updated_at": updated.isoformat() if hasattr(updated, "isoformat") else str(updated or ""),
            }
        )
    return out


def get_conversation(db, *, conversation_id: str, sub: str) -> dict[str, Any] | None:
    if db is None or not conversation_id:
        return None
    conv = db["conversations"].find_one({"id": conversation_id, "sub": sub})
    if not conv:
        return None
    rows = db["messages"].find({"conversation_id": conversation_id})
    rows = sorted(rows, key=lambda r: r.get("created_at") or datetime.min.replace(tzinfo=timezone.utc))
    messages = []
    for row in rows:
        created = row.get("created_at")
        messages.append(
            {
                "role": row.get("role") or "user",
                "content": str(row.get("content") or ""),
                "timestamp": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
                "routing_source": row.get("routing_source"),
                "status": row.get("status"),
                "rule_id": row.get("rule_id"),
                "citations": row.get("citations") or [],
                "contact_info": row.get("contact_info"),
                "interactive": row.get("interactive"),
            }
        )
    return {"conversation_id": conversation_id, "module_code": conv.get("module_code"), "messages": messages}


def _count_by(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or "") or "(trống)"
        tallies[label] = tallies.get(label, 0) + 1
    return [{"key": name, "n": n} for name, n in sorted(tallies.items(), key=lambda item: (-item[1], item[0]))]


def _empty_stats() -> dict[str, Any]:
    return {
        "turns": 0,
        "conversations": 0,
        "users": 0,
        "llm_tokens": 0,
        "avg_latency_ms": None,
        "by_status": [],
        "by_routing": [],
    }


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    conv_ids = {row.get("conversation_id") for row in rows if row.get("conversation_id")}
    users = {row.get("sub") for row in rows if row.get("sub")}
    latencies = [int(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None]
    return {
        "turns": len(rows),
        "conversations": len(conv_ids),
        "users": len(users),
        "llm_tokens": sum(int(row.get("llm_tokens") or 0) for row in rows),
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
        "by_status": _count_by(rows, "status"),
        "by_routing": _count_by(rows, "routing_source"),
    }


def summarize_chat_turns(db, *, module_code: str | None = None) -> dict[str, Any]:
    if db is None:
        return {**_empty_stats(), "by_module": []}
    rows = list(db["chat_turns"].find({}) or [])
    wanted = (module_code or "").strip()
    if wanted:
        rows = [row for row in rows if str(row.get("module_code") or "") == wanted]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get("module_code") or "") or "(trống)"
        grouped.setdefault(key, []).append(row)
    by_module = []
    for name, group in grouped.items():
        stats = _stats(group)
        by_module.append({"key": name, "n": stats["turns"], **stats})
    by_module.sort(key=lambda item: (-item["turns"], item["key"]))
    return {**_stats(rows), "by_module": by_module}
