import asyncio
import threading
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.agent.graph import AgentRuntime
from app.agent.models import ChatResult, Citation
from app.api.auth import Principal, authenticate, authorized_module

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
