from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.api.dependencies import ContextDep
from app.repositories.conversations import ConversationRepository
from app.schemas.api import ConversationDetail, ConversationList
from app.services.audit import record

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=ConversationList)
def list_conversations(
    request: Request,
    context: ContextDep,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return ConversationRepository(request.app.state.db).list(context, limit, offset)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: UUID, request: Request, context: ContextDep):
    return ConversationRepository(request.app.state.db).detail(
        str(conversation_id), context
    )


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: UUID, request: Request, context: ContextDep):
    ConversationRepository(request.app.state.db).delete(str(conversation_id), context)
    record(
        request.app.state.db,
        "delete_conversation",
        context.user.id,
        context.department,
        str(conversation_id),
    )
    return Response(status_code=204)
