from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.identity import DepartmentContext, Principal
from app.repositories.users import UserRepository
from app.schemas.api import Department
from app.services.auth import AuthService
from app.services.guest import development_guest

bearer = HTTPBearer(auto_error=False)


def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    if credentials is None and request.app.state.settings.auth_disabled:
        return development_guest(request.app.state.db)
    if credentials is None:
        raise HTTPException(
            401, "Vui lòng đăng nhập.", headers={"WWW-Authenticate": "Bearer"}
        )
    return AuthService(request.app.state.db, request.app.state.settings).authenticate(
        credentials.credentials
    )


UserDep = Annotated[Principal, Depends(current_user)]


def department_context(
    request: Request,
    user: UserDep,
    department: Annotated[Department, Header(alias="X-Department-ID")],
) -> DepartmentContext:
    role = UserRepository(request.app.state.db).role(user.id, department)
    # Even a system admin needs an explicit membership to use a department's chat.
    if role is None:
        raise HTTPException(403, "Bạn chưa được cấp quyền truy cập phòng này.")
    return DepartmentContext(user, department, role)


ContextDep = Annotated[DepartmentContext, Depends(department_context)]


def department_admin(context: ContextDep):
    if context.role != "department_admin":
        raise HTTPException(403, "Cần quyền quản trị phòng.")
    return context


AdminDep = Annotated[DepartmentContext, Depends(department_admin)]


def system_admin(user: UserDep):
    if not user.system_admin:
        raise HTTPException(403, "Cần quyền quản trị hệ thống.")
    return user


SystemAdminDep = Annotated[Principal, Depends(system_admin)]
