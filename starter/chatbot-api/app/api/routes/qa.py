from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies import require_user
from app.repositories import catalog
from app.services.module_service import live_department
from app.services.routing import resolve_module_code

router = APIRouter(prefix="/api", tags=["qa"])


@router.get("/qa")
def list_qa(
    request: Request,
    _user: Annotated[dict, Depends(require_user)],
    module_code: str | None = Query(default=None),
    mode: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """Nút FAQ sidebar: câu + câu trả lời nguyên văn File 02, release đang chạy của mảng đang chọn."""
    db = request.app.state.db
    if db is None:
        return []
    dept = live_department(getattr(request.app.state, "department", None), db)
    wanted = resolve_module_code(dept, mode=mode, module_code=module_code) if (mode or module_code) else None
    items: list[dict[str, Any]] = []
    for mod in dept.get("modules") or []:
        code = mod.get("code")
        if not code:
            continue
        if wanted and code != wanted:
            continue
        rel = catalog.get_active_release(db, code)
        if not rel:
            continue
        release_id = rel.get("release_id")
        for row in catalog.find_docs(db, "faqs", {"module_code": code, "release_id": release_id}):
            items.append(
                {
                    "id": row.get("question_code"),
                    "module_code": code,
                    "question": row.get("question") or "",
                    "answer": row.get("answer") or "",
                    "section": row.get("section") or "",
                }
            )
    return items
