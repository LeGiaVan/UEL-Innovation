from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.health import DependencyState, check_dependencies

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: dict[str, DependencyState]


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def readiness(request: Request) -> JSONResponse:
    dependencies = await check_dependencies(
        engine=request.app.state.engine,
        http_client=request.app.state.http_client,
        settings=request.app.state.settings,
    )
    is_ready = all(state == "ok" for state in dependencies.values())
    payload = ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        dependencies=dependencies,
    )
    return JSONResponse(
        content=payload.model_dump(),
        status_code=200 if is_ready else 503,
    )
