import hashlib
import secrets

from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hasher.verify(password, hashed)
    except (PwdlibError, ValueError):
        return False
