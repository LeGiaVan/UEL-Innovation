from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import require_user

router = APIRouter(prefix="/api/modules", tags=["modules"])


@router.get("")
def list_modules(
    request: Request,
    _user: Annotated[dict, Depends(require_user)],
) -> dict:
    dept = getattr(request.app.state, "department", {}) or {}
    return {"modules": dept.get("modules") or []}
