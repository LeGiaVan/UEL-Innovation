import asyncio
import json
import logging

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.dependencies import require_user
from app.services.conversation_service import load_history, save_turn
from app.services.module_service import live_department
from app.services.rate_limit_service import add_llm_tokens, check_chat_limits
from app.services.routing import resolve_module_code, route_message

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/modes")
def chat_modes(request: Request, _user: Annotated[dict, Depends(require_user)]) -> dict:
    dept = live_department(getattr(request.app.state, "department", None), request.app.state.db)
    modes = []
    for i, mod in enumerate(dept.get("modules") or [], start=1):
        modes.append(
            {
                "id": f"module_{i}",
                "code": mod.get("code") or f"module_{i}",
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
    mode: str | None = None
    trial: bool = False


@router.post("/stream")
async def chat_stream(
    body: ChatIn,
    request: Request,
    user: Annotated[dict, Depends(require_user)],
) -> StreamingResponse:
    now_fn = getattr(request.app.state, "now_fn", None)
    now = now_fn() if callable(now_fn) else None
    fail = check_chat_limits(
        request.app.state.db,
        user=user,
        message=body.message,
        department=live_department(request.app.state.department, request.app.state.db),
        trial=body.trial,
        now=now,
    )
    if fail is not None:
        headers = {}
        if fail.retry_after is not None:
            headers["Retry-After"] = str(fail.retry_after)
        raise HTTPException(status_code=fail.status, detail=fail.detail, headers=headers)

    dept = live_department(request.app.state.department, request.app.state.db)
    module_code = resolve_module_code(
        dept,
        mode=body.mode,
        module_code=body.module_code,
    )
    history = load_history(
        request.app.state.db,
        conversation_id=body.conversation_id,
        sub=str(user.get("sub") or ""),
    )
    try:
        result = await asyncio.to_thread(
            route_message,
            db=request.app.state.db,
            qdrant=getattr(request.app.state, "qdrant", None),
            department=dept,
            persona=getattr(request.app.state, "persona", None) or {},
            settings=request.app.state.settings,
            message=body.message,
            module_code=module_code or "",
            history=history,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("chat route failed")
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý câu hỏi: {exc}") from exc
    if result.llm_tokens and not body.trial:
        add_llm_tokens(
            request.app.state.db,
            sub=str(user.get("sub") or ""),
            tokens=result.llm_tokens,
            now=now,
        )
    conversation_id = body.conversation_id
    if request.app.state.db is not None:
        try:
            conversation_id = save_turn(
                request.app.state.db,
                sub=str(user.get("sub") or ""),
                conversation_id=body.conversation_id,
                module_code=result.module_code or module_code,
                user_message=body.message,
                answer=result.answer,
                routing_source=result.routing_source,
                status=result.status,
                rule_id=result.rule_id,
                citations=result.citations,
                contact_info=result.contact_info,
                interactive=result.interactive,
            )
        except Exception:  # noqa: BLE001
            log.exception("save conversation failed")

    async def events():
        done = {
            "type": "done",
            "answer": result.answer,
            "response": result.answer,
            "conversation_id": conversation_id,
            "routing_source": result.routing_source,
            "status": result.status,
            "module_code": result.module_code,
            "release_id": result.release_id,
            "rule_id": result.rule_id,
            "citations": result.citations,
            "contact_info": result.contact_info,
            "interactive": result.interactive,
        }
        yield f"data: {json.dumps({'type': 'token', 'text': result.answer}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
