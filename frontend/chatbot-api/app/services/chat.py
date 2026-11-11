import json

from uuid import uuid4

from app.repositories.conversations import ConversationRepository
from app.services.audit import record


def sse(event):
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


class ChatService:
    def __init__(self, db, provider):
        self.db, self.provider = db, provider
        self.conversations = ConversationRepository(db)

    def prepare(self, context, body):
        # Validate ownership before invoking a future provider (which may have cost).
        if body.conversation_id:
            detail = self.conversations.detail(str(body.conversation_id), context)
            if detail["mode"] != body.mode:
                from fastapi import HTTPException

                raise HTTPException(409, "Hội thoại thuộc chủ đề khác.")
        cid = str(body.conversation_id) if body.conversation_id else str(uuid4())
        complete = getattr(self.provider, "complete", None)
        if callable(complete):
            payload = complete(
                context.department,
                body.mode,
                body.message,
                conversation_id=cid,
            )
        else:
            payload = {
                "response": self.provider.answer(context.department, body.mode, body.message),
                "citations": [],
                "contact_info": None,
            }
        answer = str(payload.get("response") or "")
        cid = self.conversations.append(context, body, answer, conversation_id=cid)
        record(self.db, "chat_turn", context.user.id, context.department, cid)
        name = type(self.provider).__name__
        provider_id = "rag" if "Rag" in name else "stub"
        return {
            "type": "done",
            "response": answer,
            "conversation_id": cid,
            "user_message": body.message,
            "resolved_mode": body.mode,
            "citations": payload.get("citations") or [],
            "contact_info": payload.get("contact_info"),
            "interactive": None,
            "provider": provider_id,
        }

    def iter_sse(self, context, body):
        if body.conversation_id:
            detail = self.conversations.detail(str(body.conversation_id), context)
            if detail["mode"] != body.mode:
                from fastapi import HTTPException

                raise HTTPException(409, "Hội thoại thuộc chủ đề khác.")
        cid = str(body.conversation_id) if body.conversation_id else str(uuid4())
        stream = getattr(self.provider, "iter_sse", None)
        if callable(stream):
            yield sse({"type": "status", "label": "Đang xử lý câu hỏi…", "stage": "start"})
            done = None
            for event in stream(
                context.department,
                body.mode,
                body.message,
                conversation_id=cid,
            ):
                if event.get("type") == "done":
                    event = {
                        **event,
                        "conversation_id": cid,
                        "user_message": body.message,
                        "resolved_mode": body.mode,
                    }
                    done = event
                yield sse(event)
            if done:
                self.conversations.append(
                    context, body, str(done.get("response") or ""), conversation_id=cid
                )
                record(self.db, "chat_turn", context.user.id, context.department, cid)
            return
        result = self.prepare(context, body)
        yield from self.stream(result)

    @staticmethod
    def stream(result):
        # Stub answer is committed before delivery; disconnect never creates partial turns.
        answer = result["response"]
        for index in range(0, len(answer), 24):
            yield sse({"type": "token", "text": answer[index : index + 24]})
        yield sse(result)
