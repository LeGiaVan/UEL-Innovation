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
                "module_code": module_code,
                "preview": (user_message or "")[:100],
                "created_at": now,
                "updated_at": now,
            }
        )
    db["messages"].insert_one(
        {
            "conversation_id": cid,
            "sub": sub,
            "role": "user",
            "content": user_message,
            "created_at": now,
        }
    )
    db["messages"].insert_one(
        {
            "conversation_id": cid,
            "sub": sub,
            "role": "assistant",
            "content": answer,
            "routing_source": routing_source,
            "status": status,
            "rule_id": rule_id,
            "citations": citations or [],
            "contact_info": contact_info,
            "interactive": interactive,
            "created_at": now,
        }
    )
    db["conversations"].update_one(
        {"id": cid, "sub": sub},
        {"$set": {"updated_at": now, "module_code": module_code, "preview": (user_message or "")[:100]}},
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
