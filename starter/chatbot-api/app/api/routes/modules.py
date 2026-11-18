from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/modules", tags=["modules"])


@router.get("")
def list_modules(request: Request) -> dict:
    dept = getattr(request.app.state, "department", {}) or {}
    return {"modules": dept.get("modules") or []}
