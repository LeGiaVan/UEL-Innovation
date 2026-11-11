from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.api.dependencies import AdminDep, SystemAdminDep
from app.repositories.users import UserRepository
from app.schemas.api import Department, RoleUpdate, UserCreate, UserInfo
from app.services.audit import record

router = APIRouter(tags=["Administration"])


@router.post("/admin/users", response_model=UserInfo, status_code=201)
def create_user(body: UserCreate, request: Request, user: SystemAdminDep):
    repo = UserRepository(request.app.state.db)
    uid = repo.create(body.username, body.password.get_secret_value(), body.memberships)
    record(request.app.state.db, "create_user", user.id, target_id=uid)
    return repo.info(uid)


@router.get("/departments/members")
def members(request: Request, context: AdminDep):
    return {"members": UserRepository(request.app.state.db).members(context.department)}


@router.put("/admin/users/{user_id}/memberships/{department}", status_code=204)
def grant(
    user_id: UUID,
    department: Department,
    body: RoleUpdate,
    request: Request,
    user: SystemAdminDep,
):
    UserRepository(request.app.state.db).set_role(str(user_id), department, body.role)
    record(request.app.state.db, "grant_membership", user.id, department, str(user_id))
    return Response(status_code=204)


@router.delete("/admin/users/{user_id}/memberships/{department}", status_code=204)
def revoke(
    user_id: UUID, department: Department, request: Request, user: SystemAdminDep
):
    UserRepository(request.app.state.db).remove_role(str(user_id), department)
    record(request.app.state.db, "revoke_membership", user.id, department, str(user_id))
    return Response(status_code=204)


@router.delete("/admin/users/{user_id}/sessions", status_code=204)
def revoke_sessions(user_id: UUID, request: Request, user: SystemAdminDep):
    request.app.state.db.delete_user_sessions(str(user_id))
    record(request.app.state.db, "revoke_sessions", user.id, target_id=str(user_id))
    return Response(status_code=204)
