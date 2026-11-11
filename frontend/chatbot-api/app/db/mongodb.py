import math
import uuid

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.db.database import DuplicateUserError


class MongoDatabase:
    def __init__(self, uri: str, database_name: str):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.db = self.client[database_name]

    def initialize(self):
        self.client.admin.command("ping")
        self.db.users.create_index([("username", ASCENDING)], unique=True)
        self.db.memberships.create_index(
            [("user_id", ASCENDING), ("department", ASCENDING)], unique=True
        )
        self.db.sessions.create_index(
            [("expires_at", ASCENDING)], expireAfterSeconds=0
        )
        self.db.rate_limits.create_index(
            [("reset_at", ASCENDING)], expireAfterSeconds=0
        )
        self.db.conversations.create_index(
            [
                ("user_id", ASCENDING),
                ("department", ASCENDING),
                ("updated_at", DESCENDING),
            ]
        )
        self.db.audit_events.create_index([("timestamp", DESCENDING)])

    def close(self):
        self.client.close()

    def ping(self):
        self.client.admin.command("ping")

    def create_user(self, username, password_hash, memberships, system_admin=False):
        uid = str(uuid.uuid4())
        membership_docs = [
            {"department": m.department, "role": m.role} for m in memberships
        ]
        if len({m["department"] for m in membership_docs}) != len(membership_docs):
            raise DuplicateUserError
        try:
            self.db.users.insert_one(
                {
                    "_id": uid,
                    "username": username,
                    "password_hash": password_hash,
                    "active": True,
                    "system_admin": system_admin,
                    "created_at": _now(),
                }
            )
        except DuplicateKeyError as exc:
            raise DuplicateUserError from exc
        if membership_docs:
            self.db.memberships.insert_many(
                [
                    {"user_id": uid, **membership}
                    for membership in membership_docs
                ]
            )
        return uid

    def user_by_username(self, username):
        user = self.db.users.find_one({"username": username})
        return _user(user) if user else None

    def user_info(self, uid):
        user = self.db.users.find_one(
            {"_id": uid, "active": True},
            {"username": 1, "system_admin": 1},
        )
        if not user:
            return None
        memberships = list(
            self.db.memberships.find(
                {"user_id": uid}, {"_id": 0, "department": 1, "role": 1}
            ).sort("department", ASCENDING)
        )
        return {
            "id": user["_id"],
            "username": user["username"],
            "system_admin": bool(user["system_admin"]),
            "memberships": memberships,
        }

    def user_role(self, uid, department):
        membership = self.db.memberships.find_one(
            {"user_id": uid, "department": department}, {"role": 1}
        )
        return membership["role"] if membership else None

    def user_members(self, department):
        memberships = self.db.memberships.find({"department": department})
        result = []
        for membership in memberships:
            user = self.db.users.find_one(
                {"_id": membership["user_id"], "active": True},
                {"username": 1},
            )
            if user:
                result.append(
                    {
                        "id": user["_id"],
                        "username": user["username"],
                        "role": membership["role"],
                    }
                )
        return result

    def set_user_role(self, uid, department, role):
        if not self.db.users.find_one({"_id": uid, "active": True}, {"_id": 1}):
            return False
        self.db.memberships.update_one(
            {"user_id": uid, "department": department},
            {"$set": {"role": role}},
            upsert=True,
        )
        return True

    def remove_user_role(self, uid, department):
        self.db.memberships.delete_one({"user_id": uid, "department": department})

    def create_session(self, token_hash, user_id, expires_at):
        self.db.sessions.insert_one(
            {"_id": token_hash, "user_id": user_id, "expires_at": expires_at}
        )

    def authenticated_user(self, token_hash, now):
        session = self.db.sessions.find_one(
            {"_id": token_hash, "expires_at": {"$gt": now}}
        )
        if not session:
            return None
        user = self.db.users.find_one({"_id": session["user_id"], "active": True})
        return _user(user) if user else None

    def delete_session(self, token_hash):
        self.db.sessions.delete_one({"_id": token_hash})

    def delete_user_sessions(self, user_id):
        self.db.sessions.delete_many({"user_id": user_id})

    def record_audit(self, actor_id, department, action, target_id, timestamp):
        self.db.audit_events.insert_one(
            {
                "actor_id": actor_id,
                "department": department,
                "action": action,
                "target_id": target_id,
                "timestamp": timestamp,
            }
        )

    def ensure_guest(self, guest_id, departments, timestamp):
        self.db.users.update_one(
            {"_id": guest_id},
            {
                "$setOnInsert": {
                    "username": "_development_guest",
                    "password_hash": "!",
                    "active": True,
                    "system_admin": False,
                    "created_at": timestamp,
                }
            },
            upsert=True,
        )
        for department in departments:
            self.db.memberships.update_one(
                {"user_id": guest_id, "department": department},
                {"$setOnInsert": {"role": "member"}},
                upsert=True,
            )

    def check_rate_limit(self, key, limit, now, window):
        active_window = {"_id": key, "reset_at": {"$gt": now}, "count": {"$lt": limit}}
        updated = self.db.rate_limits.find_one_and_update(
            active_window,
            {"$inc": {"count": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if updated:
            return None

        expired = self.db.rate_limits.update_one(
            {"_id": key, "reset_at": {"$lte": now}},
            {"$set": {"count": 1, "reset_at": now + window}},
        )
        if expired.matched_count:
            return None

        try:
            self.db.rate_limits.insert_one(
                {"_id": key, "count": 1, "reset_at": now + window}
            )
            return None
        except DuplicateKeyError:
            updated = self.db.rate_limits.find_one_and_update(
                active_window,
                {"$inc": {"count": 1}},
                return_document=ReturnDocument.AFTER,
            )
            if updated:
                return None
            row = self.db.rate_limits.find_one({"_id": key})
            if row and row["reset_at"] > now:
                return max(1, math.ceil(row["reset_at"] - now))
            return self.check_rate_limit(key, limit, now, window)

    def append_turn(self, conversation, message):
        cid = conversation["id"]
        message_doc = {
            "user_message": message["user_message"],
            "assistant_response": message["assistant_response"],
            "timestamp": message["timestamp"],
        }
        if conversation["is_new"]:
            self.db.conversations.insert_one(
                {
                    "_id": cid,
                    "user_id": conversation["user_id"],
                    "department": conversation["department"],
                    "mode": conversation["mode"],
                    "preview": conversation["preview"],
                    "created_at": conversation["timestamp"],
                    "updated_at": conversation["timestamp"],
                    "messages": [message_doc],
                }
            )
            return "ok"

        result = self.db.conversations.update_one(
            {
                "_id": cid,
                "user_id": conversation["user_id"],
                "department": conversation["department"],
                "mode": conversation["mode"],
            },
            {
                "$push": {"messages": message_doc},
                "$set": {"updated_at": conversation["timestamp"]},
            },
        )
        if result.matched_count:
            return "ok"
        row = self.db.conversations.find_one(
            {
                "_id": cid,
                "user_id": conversation["user_id"],
                "department": conversation["department"],
            },
            {"mode": 1},
        )
        return "mode_conflict" if row else "not_found"

    def conversation(self, cid, user_id, department):
        row = self.db.conversations.find_one(
            {"_id": cid, "user_id": user_id, "department": department}
        )
        return _conversation(row) if row else None

    def list_conversations(self, user_id, department, limit, offset):
        rows = self.db.conversations.find(
            {"user_id": user_id, "department": department},
            {
                "_id": 1,
                "mode": 1,
                "preview": 1,
                "created_at": 1,
                "updated_at": 1,
            },
        ).sort([("updated_at", DESCENDING), ("_id", DESCENDING)]).skip(offset).limit(
            limit
        )
        return [
            {
                "id": row["_id"],
                "conversation_id": row["_id"],
                "mode": row["mode"],
                "preview": row["preview"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def conversation_messages(self, cid):
        row = self.db.conversations.find_one({"_id": cid}, {"messages": 1})
        return row.get("messages", []) if row else []

    def delete_conversation(self, cid):
        self.db.conversations.delete_one({"_id": cid})

    def cleanup(self, now):
        self.db.sessions.delete_many({"expires_at": {"$lte": now}})
        self.db.rate_limits.delete_many({"reset_at": {"$lte": now}})


def _now():
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def _user(document):
    return {
        "id": document["_id"],
        "username": document["username"],
        "password_hash": document["password_hash"],
        "active": document["active"],
        "system_admin": document["system_admin"],
        "created_at": document["created_at"],
    }


def _conversation(document):
    return {
        "id": document["_id"],
        "user_id": document["user_id"],
        "department": document["department"],
        "mode": document["mode"],
        "preview": document["preview"],
        "created_at": document["created_at"],
        "updated_at": document["updated_at"],
    }
