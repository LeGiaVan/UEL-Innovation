import asyncio
import json
import threading
from collections.abc import AsyncIterator, Iterator
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.agent.graph import AgentRuntime
from app.agent.models import ChatResult, Citation
from app.api.auth import Principal, authenticate, authorized_module

STAGE_LABELS = {
    "start": "Đang xử lý câu hỏi…",
    "normalize_input": "Đang đọc câu hỏi…",
    "routing_check": "Đang xác định phạm vi hỗ trợ…",
    "faq_match": "Đang đối chiếu câu hỏi thường gặp…",
    "retrieve": "Đang tìm trong tài liệu đã duyệt…",
    "generate": "Đang soạn câu trả lời…",
}

router = APIRouter(prefix="/v1", tags=["chat"])
_runtime_lock = threading.Lock()


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "message": "Hello",
                    "conversation_id": "5a7f17f0-b0f6-4aad-bc0b-f9b7d5e970a1",
                }
            ]
        },
    )
    message: str = Field(min_length=1, max_length=4000, pattern=r".*\S.*")
    conversation_id: UUID | None = None
    module_code: str | None = Field(default=None, pattern=r"^[a-z0-9_]+$")


class ChatResponse(BaseModel):
    request_id: str
    conversation_id: UUID
    status: str
    answer: str
    provider_fallback: bool = False
    citations: list[Citation]
    support_contact: str | None = None
    contact_information: str | None = None
    online_channel: str | None = None
    rule_id: str | None = None
    rule_version: str | None = None


def _chat_response(request: Request, conversation_id: UUID, result: ChatResult) -> ChatResponse:
    return ChatResponse(
        request_id=request.state.request_id,
        conversation_id=conversation_id,
        status=result.status,
        answer=result.answer,
        provider_fallback=bool(result.error_message and result.status == "answered"),
        citations=result.citations,
        support_contact=result.support_contact,
        contact_information=result.contact_information,
        online_channel=result.online_channel,
        rule_id=result.rule_id,
        rule_version=result.rule_version,
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _answer_chunks(text: str, size: int = 32) -> Iterator[str]:
    for index in range(0, len(text), size):
        yield text[index : index + size]


def _collect_stream(
    request: Request, body: ChatRequest, conversation_id: UUID, principal: Principal
) -> tuple[list[str], ChatResult]:
    settings = request.app.state.settings
    with _runtime_lock:
        if not hasattr(request.app.state, "agent_runtime"):
            request.app.state.agent_runtime = AgentRuntime.from_settings(settings)
        runtime = request.app.state.agent_runtime
    iterator = getattr(runtime, "iter_progress", None)
    if callable(iterator):
        stages: list[str] = []
        final: ChatResult | None = None
        for stage, item in iterator(
            body.message,
            department_id=principal.department_id,
            module_code=body.module_code or principal.modules[0],
            environment=settings.app_env,
            conversation_id=str(conversation_id),
            principal_id=principal.id,
        ):
            if item is None:
                stages.append(str(stage))
            else:
                final = item
        if final is None:
            raise RuntimeError("Chat stream produced no result")
        return stages, final
    return ["generate"], _invoke(request, body, conversation_id, principal)


def _invoke(
    request: Request, body: ChatRequest, conversation_id: UUID, principal: Principal
) -> ChatResult:
    settings = request.app.state.settings
    with _runtime_lock:
        if not hasattr(request.app.state, "agent_runtime"):
            request.app.state.agent_runtime = AgentRuntime.from_settings(settings)
        runtime: AgentRuntime = request.app.state.agent_runtime
    return runtime.invoke(
        body.message,
        department_id=principal.department_id,
        module_code=body.module_code or principal.modules[0],
        environment=settings.app_env,
        conversation_id=str(conversation_id),
        principal_id=principal.id,
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={401: {"description": "Invalid API key"}, 504: {"description": "Request timed out"}},
)
async def chat(
    body: ChatRequest, request: Request, principal: Annotated[Principal, Depends(authenticate)]
) -> ChatResponse:
    settings = request.app.state.settings
    _, module = authorized_module(request, principal, body.module_code)
    body.module_code = module.code
    conversation_id = body.conversation_id or uuid4()
    try:
        async with asyncio.timeout(settings.chat_timeout_seconds):
            result = await run_in_threadpool(_invoke, request, body, conversation_id, principal)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Chat request timed out") from None
    except Exception:
        raise HTTPException(status_code=503, detail="Chat service unavailable") from None
    return _chat_response(request, conversation_id, result)


@router.post(
    "/chat/stream",
    responses={401: {"description": "Invalid API key"}, 504: {"description": "Request timed out"}},
)
async def chat_stream(
    body: ChatRequest, request: Request, principal: Annotated[Principal, Depends(authenticate)]
) -> StreamingResponse:
    settings = request.app.state.settings
    _, module = authorized_module(request, principal, body.module_code)
    body.module_code = module.code
    conversation_id = body.conversation_id or uuid4()

    async def events() -> AsyncIterator[str]:
        yield _sse("status", {"stage": "start", "label": STAGE_LABELS["start"]})
        try:
            async with asyncio.timeout(settings.chat_timeout_seconds):
                stages, result = await run_in_threadpool(
                    _collect_stream, request, body, conversation_id, principal
                )
        except TimeoutError:
            yield _sse("error", {"detail": "Chat request timed out"})
            return
        except Exception:
            yield _sse("error", {"detail": "Chat service unavailable"})
            return
        for stage in stages:
            label = STAGE_LABELS.get(stage)
            if label:
                yield _sse("status", {"stage": stage, "label": label})
        for chunk in _answer_chunks(result.answer):
            yield _sse("token", {"text": chunk})
        yield _sse(
            "done",
            _chat_response(request, conversation_id, result).model_dump(mode="json"),
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class ModuleList(BaseModel):
    department_id: str
    modules: list[dict[str, str]]


@router.get("/modules", response_model=ModuleList)
async def modules(
    request: Request, principal: Annotated[Principal, Depends(authenticate)]
) -> dict[str, Any]:
    output = []
    for code in principal.modules:
        try:
            _, module = authorized_module(request, principal, code)
            output.append({"code": module.code, "name": module.name})
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
    return {"department_id": principal.department_id, "modules": output}
