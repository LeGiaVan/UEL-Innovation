from datetime import UTC, datetime

from fastapi import HTTPException

from app.core.security import password_hasher
from app.db.database import DuplicateUserError


def now():
    return datetime.now(UTC).isoformat()


class UserRepository:
    def __init__(self, db):
        self.db = db

    def create(self, username, password, memberships, system_admin=False):
        hashed = password_hasher.hash(password)
        try:
            return self.db.create_user(
                username.lower(), hashed, memberships, system_admin
            )
        except DuplicateUserError:
            raise HTTPException(409, "Tài khoản đã tồn tại hoặc phòng bị lặp.")

    def by_username(self, username):
        return self.db.user_by_username(username.lower())

    def info(self, uid):
        result = self.db.user_info(uid)
        if not result:
            raise HTTPException(404, "Không tìm thấy tài khoản.")
        return result

    def role(self, uid, department):
        return self.db.user_role(uid, department)

    def members(self, department):
        return self.db.user_members(department)

    def set_role(self, uid, department, role):
        if not self.db.set_user_role(uid, department, role):
            raise HTTPException(404, "Không tìm thấy tài khoản.")

    def remove_role(self, uid, department):
        self.db.remove_user_role(uid, department)
