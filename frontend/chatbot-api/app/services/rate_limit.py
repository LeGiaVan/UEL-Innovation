import hashlib
import time

from fastapi import HTTPException


class RateLimiter:
    def __init__(self, db):
        self.db = db

    def check(self, key, limit, window=60):
        key = hashlib.sha256(key.encode()).hexdigest()
        now = time.time()
        retry = self.db.check_rate_limit(key, limit, now, window)
        if retry is not None:
            raise HTTPException(
                429,
                "Bạn gửi yêu cầu quá nhanh. Vui lòng thử lại sau.",
                headers={"Retry-After": str(retry)},
            )
