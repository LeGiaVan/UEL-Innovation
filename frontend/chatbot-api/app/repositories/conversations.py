import uuid

from fastapi import HTTPException

from app.repositories.users import now


class ConversationRepository:
    def __init__(self, db):
        self.db = db

    def owned(self, conn, cid, context):
        row = self.db.conversation(cid, context.user.id, context.department)
        if not row:
            raise HTTPException(404, "Không tìm thấy hội thoại.")
        return row

    def append(self, context, body, answer, *, conversation_id: str | None = None):
        cid = (
            str(body.conversation_id)
            if body.conversation_id
            else (conversation_id or str(uuid.uuid4()))
        )
        timestamp = now()
        status = self.db.append_turn(
            {
                "id": cid,
                "user_id": context.user.id,
                "department": context.department,
                "mode": body.mode,
                "preview": body.message[:100],
                "timestamp": timestamp,
                "is_new": body.conversation_id is None,
            },
            {
                "user_message": body.message,
                "assistant_response": answer,
                "timestamp": timestamp,
            },
        )
        if status == "not_found":
            raise HTTPException(404, "Không tìm thấy hội thoại.")
        if status == "mode_conflict":
            raise HTTPException(409, "Hội thoại thuộc chủ đề khác.")
        return cid

    def list(self, context, limit, offset):
        return {
            "conversations": self.db.list_conversations(
                context.user.id, context.department, limit, offset
            )
        }

    def detail(self, cid, context):
        row = self.owned(None, cid, context)
        return {
            "conversation_id": cid,
            "mode": row["mode"],
            "messages": self.db.conversation_messages(cid),
        }

    def delete(self, cid, context):
        self.owned(None, cid, context)
        self.db.delete_conversation(cid)
