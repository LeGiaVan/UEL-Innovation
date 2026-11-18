from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request

from app.core.security import COOKIE_NAME, decode_session_jwt
from app.repositories.sessions import get_active_session


def department_id(request: Request) -> str:
    """Không lấy mã phòng từ client."""
    return request.app.state.department_id


def optional_user(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    settings = request.app.state.settings
    try:
        payload = decode_session_jwt(token, settings.jwt_secret)
    except jwt.PyJWTError:
        return None
    if payload.get("department_id") != request.app.state.department_id:
        return None
    db = request.app.state.db
    if db is None:
        return None
    session = get_active_session(db, payload.get("sid") or "")
    if session is None:
        return None
    return {
        "sub": payload["sub"],
        "email": payload["email"],
        "role": payload["role"],
        "department_id": request.app.state.department_id,
        "sid": payload["sid"],
        "authenticated": True,
    }


def require_user(user: Annotated[dict[str, Any] | None, Depends(optional_user)]) -> dict[str, Any]:
    if not user:
        raise HTTPException(status_code=401, detail="Cần đăng nhập Google")
    return user


def require_admin(user: Annotated[dict[str, Any], Depends(require_user)]) -> dict[str, Any]:
    if user.get("role") != "department_admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị phòng")
    return user
