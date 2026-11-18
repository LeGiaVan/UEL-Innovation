import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/modes")
def chat_modes(request: Request) -> dict:
    dept = getattr(request.app.state, "department", {}) or {}
    modes = []
    for i, mod in enumerate(dept.get("modules") or [], start=1):
        modes.append(
            {
                "id": f"module_{i}",
                "label": mod.get("name") or mod.get("code") or f"module_{i}",
            }
        )
    if not modes:
        modes = [{"id": "module_1", "label": "Chat"}]
    return {"modes": modes}


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=20000)
    conversation_id: str | None = None
    module_code: str | None = None


@router.post("/stream")
async def chat_stream(body: ChatIn, request: Request) -> StreamingResponse:
    """P0 stub. Routing 4 tầng + RAG ở P4. Không đọc RAG_ROUTES, không Postgres."""

    async def events():
        answer = (
            "Đây là khung P0. Câu hỏi đã nhận, chưa tra FAQ/Excel. "
            "Routing 4 tầng và RAG gắn ở P4."
        )
        yield f"data: {json.dumps({'type': 'token', 'text': answer}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'answer': answer, 'conversation_id': body.conversation_id, 'routing_source': None}, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
