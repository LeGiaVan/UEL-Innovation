from typing import Annotated, Any
from queue import Queue

import asyncio
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.api.dependencies import require_admin
from app.services.conversation_service import summarize_chat_turns
from app.services.ingest_service import IngestError, check_module, ingest_module
from app.services.module_service import (
    ModuleIn,
    add_module,
    live_department,
    load_department_yaml,
    resolve_department_yaml,
)
from app.services.persona_service import (
    PersonaIn,
    active_topics,
    public_persona,
    stale_regex,
    write_audit,
)
from app.repositories import catalog

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _dept(request: Request) -> dict:
    return live_department(request.app.state.department or {}, request.app.state.db)


def _module_counts(db, code: str, release_id: str | None) -> dict[str, int]:
    if db is None or not code or not release_id:
        return {"rules": 0, "faqs": 0, "milestones": 0}
    filt = {"module_code": code, "release_id": release_id}
    return {
        "rules": db["routing_rules"].count_documents(filt),
        "faqs": db["faqs"].count_documents(filt),
        "milestones": db["milestones"].count_documents(filt),
    }


def _modules(request: Request) -> list[dict]:
    db = request.app.state.db
    out = []
    for mod in _dept(request).get("modules") or []:
        code = mod.get("code")
        rel = catalog.get_active_release(db, code) if db is not None and code else None
        release_id = (rel or {}).get("release_id")
        out.append(
            {
                "code": code,
                "name": mod.get("name") or code,
                "release_id": release_id,
                "checksums": (rel or {}).get("checksums") or {},
                "warnings": (rel or {}).get("warnings") or [],
                "counts": _module_counts(db, code, release_id),
            }
        )
    return out


@router.get("/status")
def admin_status(request: Request, _admin: Annotated[dict, Depends(require_admin)]) -> dict:
    modules = _modules(request)
    return {
        "ingest": "ready",
        "persona": "ready",
        "releases": [{"module_code": m["code"], "release_id": m["release_id"]} for m in modules],
        "modules": modules,
    }


@router.get("/analytics")
def admin_analytics(
    request: Request,
    _admin: Annotated[dict, Depends(require_admin)],
    module_code: str | None = None,
) -> dict:
    return summarize_chat_turns(request.app.state.db, module_code=module_code)


@router.get("/releases")
def list_releases(
    request: Request,
    _admin: Annotated[dict, Depends(require_admin)],
    module_code: str,
) -> dict:
    db = request.app.state.db
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB chưa sẵn sàng")
    docs = catalog.find_docs(db, "releases", {"module_code": module_code})
    return {"releases": [{k: v for k, v in d.items() if k != "_id"} for d in docs]}


@router.get("/topics")
def list_topics(
    request: Request,
    _admin: Annotated[dict, Depends(require_admin)],
    module_code: str | None = None,
) -> dict:
    topics = active_topics(request.app.state.db, _dept(request))
    if module_code:
        topics = [row for row in topics if row["module_code"] == module_code]
    return {"topics": topics}


@router.get("/persona")
def get_persona(request: Request, _admin: Annotated[dict, Depends(require_admin)]) -> dict:
    persona = public_persona(getattr(request.app.state, "persona", None) or {})
    db = request.app.state.db
    topics = active_topics(db, _dept(request))
    known = {row["rule_id"] for row in topics}
    return {
        "persona": persona,
        "source": "yaml",
        "readonly": True,
        "config_path": "chatbot-api/configs/persona.yaml",
        "updated_at": "",
        "updated_by": "",
        "stale_regex": stale_regex(persona.get("routing_regex") or [], known),
        "topics": topics,
        "modules": _modules(request),
    }


@router.put("/persona")
def put_persona(
    _request: Request,
    _body: PersonaIn,
    _admin: Annotated[dict, Depends(require_admin)],
) -> dict:
    raise HTTPException(
        status_code=405,
        detail="Cách bot trả lời chỉ sửa trong chatbot-api/configs/persona.yaml, rồi khởi động lại dịch vụ.",
    )


async def _read_pack(
    file_01: UploadFile,
    file_02: UploadFile,
    file_03: UploadFile,
    file_04: UploadFile,
    file_05: UploadFile,
) -> tuple[dict[int, bytes], dict[int, str]]:
    blobs = {
        1: await file_01.read(),
        2: await file_02.read(),
        3: await file_03.read(),
        4: await file_04.read(),
        5: await file_05.read(),
    }
    names = {
        1: file_01.filename or "1.xlsx",
        2: file_02.filename or "2.xlsx",
        3: file_03.filename or "3.xlsx",
        4: file_04.filename or "4.xlsx",
        5: file_05.filename or "5.xlsx",
    }
    return blobs, names


@router.post("/ingest/check")
async def ingest_check(
    request: Request,
    _admin: Annotated[dict, Depends(require_admin)],
    module_code: Annotated[str, Form()],
    file_01: Annotated[UploadFile, File()],
    file_02: Annotated[UploadFile, File()],
    file_03: Annotated[UploadFile, File()],
    file_04: Annotated[UploadFile, File()],
    file_05: Annotated[UploadFile, File()],
) -> dict:
    blobs, _names = await _read_pack(file_01, file_02, file_03, file_04, file_05)
    try:
        return await asyncio.to_thread(
            check_module,
            department=_dept(request),
            module_code=module_code,
            files=blobs,
        )
    except IngestError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


@router.post("/ingest")
async def ingest(
    request: Request,
    admin: Annotated[dict, Depends(require_admin)],
    module_code: Annotated[str, Form()],
    file_01: Annotated[UploadFile, File()],
    file_02: Annotated[UploadFile, File()],
    file_03: Annotated[UploadFile, File()],
    file_04: Annotated[UploadFile, File()],
    file_05: Annotated[UploadFile, File()],
) -> dict:
    blobs, names = await _read_pack(file_01, file_02, file_03, file_04, file_05)
    try:
        result = await asyncio.to_thread(
            ingest_module,
            db=request.app.state.db,
            qdrant=getattr(request.app.state, "qdrant", None),
            data_dir=request.app.state.settings.chatbot_data_dir,
            department=_dept(request),
            module_code=module_code,
            files=blobs,
            filenames=names,
            embed_dim=request.app.state.settings.embed_dim,
            embed_backend=getattr(request.app.state.settings, "embed_backend", "hash"),
        )
    except IngestError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    write_audit(
        request.app.state.db,
        action="ingest",
        email=str(admin.get("email") or ""),
        meta={"module_code": module_code, "release_id": result.get("release_id")},
    )
    return result


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


@router.post("/ingest/stream")
async def ingest_stream(
    request: Request,
    admin: Annotated[dict, Depends(require_admin)],
    module_code: Annotated[str, Form()],
    file_01: Annotated[UploadFile, File()],
    file_02: Annotated[UploadFile, File()],
    file_03: Annotated[UploadFile, File()],
    file_04: Annotated[UploadFile, File()],
    file_05: Annotated[UploadFile, File()],
) -> StreamingResponse:
    blobs, names = await _read_pack(file_01, file_02, file_03, file_04, file_05)
    events: Queue = Queue()

    def on_progress(event: dict[str, Any]) -> None:
        events.put(event)

    def worker() -> None:
        try:
            result = ingest_module(
                db=request.app.state.db,
                qdrant=getattr(request.app.state, "qdrant", None),
                data_dir=request.app.state.settings.chatbot_data_dir,
                department=_dept(request),
                module_code=module_code,
                files=blobs,
                filenames=names,
                embed_dim=request.app.state.settings.embed_dim,
                embed_backend=getattr(request.app.state.settings, "embed_backend", "hash"),
                on_progress=on_progress,
            )
            write_audit(
                request.app.state.db,
                action="ingest",
                email=str(admin.get("email") or ""),
                meta={"module_code": module_code, "release_id": result.get("release_id")},
            )
            events.put({"type": "done", **result})
        except IngestError as exc:
            events.put({"type": "error", "status": exc.status, "detail": exc.detail})
        except Exception as exc:  # noqa: BLE001
            events.put({"type": "error", "status": 500, "detail": str(exc)})
        finally:
            events.put(None)

    async def gen():
        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(None, worker)
        yield _sse({"type": "progress", "step": "parse", "pct": 2, "message": "Bắt đầu cập nhật dữ liệu…"})
        while True:
            item = await loop.run_in_executor(None, events.get)
            if item is None:
                break
            yield _sse(item)
        await task

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/modules")
def create_module(
    request: Request,
    body: ModuleIn,
    admin: Annotated[dict, Depends(require_admin)],
) -> dict:
    db = request.app.state.db
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB chưa sẵn sàng")
    try:
        yaml_path = resolve_department_yaml(request.app.state.settings.department_yaml)
        created = add_module(
            db,
            request.app.state.department or {},
            name=body.name,
            email=str(admin.get("email") or ""),
            data_dir=request.app.state.settings.chatbot_data_dir,
            yaml_path=yaml_path,
        )
        loaded = load_department_yaml(yaml_path)
        if loaded:
            request.app.state.department = loaded
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    write_audit(
        db,
        action="module_add",
        email=str(admin.get("email") or ""),
        meta=created,
    )
    return {"module": created, "modules": _modules(request)}
