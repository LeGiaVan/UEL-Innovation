import secrets
import time

from fastapi import HTTPException

from app.core.security import DUMMY_HASH, hash_token, verify_password
from app.models.identity import Principal
from app.repositories.users import UserRepository
from app.services.audit import record


class AuthService:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings
        self.users = UserRepository(db)

    def login(self, username, password):
        user = self.users.by_username(username)
        valid = verify_password(password, user["password_hash"] if user else DUMMY_HASH)
        if not user or not valid or not user["active"]:
            record(self.db, "login_failed")
            raise HTTPException(
                401,
                "Tên đăng nhập hoặc mật khẩu không đúng.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = secrets.token_urlsafe(32)
        self.db.create_session(
            hash_token(token),
            user["id"],
            time.time() + self.settings.session_ttl_seconds,
        )
        record(self.db, "login", user["id"])
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": self.settings.session_ttl_seconds,
            "user": self.users.info(user["id"]),
        }

    def authenticate(self, token):
        user = self.db.authenticated_user(hash_token(token), time.time())
        if not user:
            raise HTTPException(
                401,
                "Phiên đăng nhập không hợp lệ hoặc đã hết hạn.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return Principal(user["id"], user["username"], bool(user["system_admin"]))

    def logout(self, token):
        self.db.delete_session(hash_token(token))
