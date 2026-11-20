from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import optional_user
from app.core.security import COOKIE_NAME, encode_session_jwt, resolve_role
from app.repositories.sessions import create_session, revoke_session
from app.repositories.users import upsert_google_user
from app.services.auth_service import GoogleTokenError, verify_google_id_token
from app.services.persona_service import public_persona

router = APIRouter(prefix="/api/auth", tags=["auth"])


class GoogleIn(BaseModel):
    """Chỉ nhận id_token. role / department_id từ client bị bỏ qua."""

    model_config = ConfigDict(extra="ignore")
    id_token: str = Field(..., min_length=20)


def _set_session_cookie(response: Response, token: str, settings) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=bool(settings.cookie_secure),
        max_age=int(settings.jwt_ttl_hours * 3600),
        path="/",
    )


def _public_department(request: Request) -> dict:
    dept = request.app.state.department or {}
    code = str(request.app.state.department_id or dept.get("id") or "").strip()
    name = str(dept.get("name") or "").strip() or "Trợ lý UEL"
    short = str(dept.get("short") or "").strip() or (
        "P.Starter" if not code or code == "starter" else f"P.{code.upper()}"
    )
    return {"id": code or "starter", "name": name, "short": short}


@router.get("/config")
def auth_config(request: Request) -> dict:
    persona = public_persona(getattr(request.app.state, "persona", None) or {})
    return {
        "google_client_id": request.app.state.settings.google_client_id or "",
        "department": _public_department(request),
        "greeting": str(persona.get("greeting") or "").strip(),
    }


@router.get("/me")
def me(request: Request) -> dict:
    user = optional_user(request)
    if not user:
        return {"authenticated": False}
    return user


@router.post("/google")
def google_login(body: GoogleIn, request: Request, response: Response) -> dict:
    settings = request.app.state.settings
    db = request.app.state.db
    if not settings.google_client_id:
        raise HTTPException(
            status_code=503,
            detail="Chưa có GOOGLE_CLIENT_ID trong .env",
        )
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB chưa sẵn sàng — chạy mongo rồi thử lại")
    verify = getattr(request.app.state, "verify_google_id_token", verify_google_id_token)
    try:
        info = verify(body.id_token, settings.google_client_id)
    except GoogleTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    email = str(info["email"]).strip().lower()
    sub = str(info["sub"])
    department = request.app.state.department or {}
    role = resolve_role(
        email,
        department.get("admins") or [],
        allow_non_uel_admin=bool(department.get("allow_non_uel_admin")),
    )
    department_id = request.app.state.department_id
    sid = str(uuid4())
    ttl = settings.jwt_ttl_hours
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)

    upsert_google_user(db, sub=sub, email=email)
    create_session(db, sid=sid, sub=sub, email=email, expires_at=expires_at)
    token = encode_session_jwt(
        secret=settings.jwt_secret,
        sub=sub,
        email=email,
        role=role,
        department_id=department_id,
        sid=sid,
        ttl_hours=ttl,
    )
    _set_session_cookie(response, token, settings)
    return {
        "authenticated": True,
        "email": email,
        "role": role,
        "department_id": department_id,
    }


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    user = optional_user(request)
    db = request.app.state.db
    if user and db is not None:
        revoke_session(db, user["sid"])
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
