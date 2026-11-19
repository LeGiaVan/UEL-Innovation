from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import require_user
from app.services import conversation_service as conv_svc

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
def list_conversations_route(
    request: Request,
    user: Annotated[dict, Depends(require_user)],
) -> dict:
    rows = conv_svc.list_conversations(request.app.state.db, sub=str(user.get("sub") or ""))
    return {"conversations": rows}


@router.get("/{conversation_id}")
def get_conversation_route(
    conversation_id: str,
    request: Request,
    user: Annotated[dict, Depends(require_user)],
) -> dict:
    body = conv_svc.get_conversation(
        request.app.state.db,
        conversation_id=conversation_id,
        sub=str(user.get("sub") or ""),
    )
    if not body:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại")
    return body
