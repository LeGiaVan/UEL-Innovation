from fastapi import APIRouter, Request

from app.api.dependencies import UserDep
from app.api.routes import admin, auth, chat, conversations
from app.repositories.users import UserRepository
from app.services.catalog import CATALOG

router = APIRouter(prefix="/api")
for child in (auth.router, chat.router, conversations.router, admin.router):
    router.include_router(child)


@router.get("/departments", tags=["Departments"])
def departments(request: Request, user: UserDep):
    memberships = UserRepository(request.app.state.db).info(user.id)["memberships"]
    return {
        "departments": [
            {**m, "id": m["department"], "name": CATALOG[m["department"]]["name"]}
            for m in memberships
        ]
    }
