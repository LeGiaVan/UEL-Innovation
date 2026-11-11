from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies import UserDep, bearer
from app.repositories.users import UserRepository
from app.schemas.api import LoginRequest, TokenResponse, UserInfo
from app.services.audit import record
from app.services.auth import AuthService
from app.services.rate_limit import RateLimiter

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request):
    limiter = RateLimiter(request.app.state.db)
    # Do not trust X-Forwarded-For supplied by an arbitrary client.
    ip = request.client.host if request.client else "unknown"
    limiter.check(f"login:ip:{ip}", request.app.state.settings.login_limit, 60)
    limiter.check(
        f"login:user:{body.username.lower()}",
        request.app.state.settings.login_limit,
        60,
    )
    return AuthService(request.app.state.db, request.app.state.settings).login(
        body.username, body.password.get_secret_value()
    )


@router.get("/me", response_model=UserInfo)
def me(request: Request, user: UserDep):
    return UserRepository(request.app.state.db).info(user.id)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    user: UserDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
):
    if credentials is not None:
        AuthService(request.app.state.db, request.app.state.settings).logout(
            credentials.credentials
        )
    record(request.app.state.db, "logout", user.id)
    return Response(status_code=204)
