from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import ContextDep
from app.schemas.api import ChatRequest, ModesResponse, QAItem
from app.services.catalog import modes, questions
from app.services.chat import ChatService
from app.services.rate_limit import RateLimiter

router = APIRouter(tags=["Chat"])


@router.get("/chat/modes", response_model=ModesResponse)
def chat_modes(context: ContextDep):
    return {"modes": modes(context.department)}


@router.get("/qa", response_model=list[QAItem])
def qa(context: ContextDep):
    return questions(context.department)


@router.post(
    "/chat/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE token/done; backend stub",
        },
        429: {"description": "Rate limited; Retry-After seconds"},
    },
)
def chat_stream(body: ChatRequest, request: Request, context: ContextDep):
    RateLimiter(request.app.state.db).check(
        f"chat:{context.user.id}:{context.department}",
        request.app.state.settings.chat_limit,
    )
    service = ChatService(request.app.state.db, request.app.state.provider)
    return StreamingResponse(
        service.iter_sse(context, body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
