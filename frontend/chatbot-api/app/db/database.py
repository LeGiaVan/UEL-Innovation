import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class DuplicateUserError(Exception):
    pass


class Database:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(Path(__file__).with_name("migrations.sql").read_text())
            version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_versions"
            ).fetchone()[0]
            if version < 2:
                conn.executescript(
                    """
                    CREATE TABLE memberships_v2 (
                     user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                     department TEXT NOT NULL CHECK(department IN ('dbcl','qtts','pdt','pns','hc','ctsv','khcn')),
                     role TEXT NOT NULL CHECK(role IN ('member','department_admin')),
                     PRIMARY KEY(user_id, department)
                    );
                    INSERT INTO memberships_v2 SELECT * FROM memberships;
                    DROP TABLE memberships;
                    ALTER TABLE memberships_v2 RENAME TO memberships;
                    INSERT INTO schema_versions(version) VALUES (2);
                    """
                )

    def close(self):
        pass

    def ping(self):
        with self.connect() as conn:
            conn.execute("SELECT version FROM schema_versions LIMIT 1").fetchone()

    def create_user(self, username, password_hash, memberships, system_admin=False):
        uid = str(uuid.uuid4())
        try:
            with self.connect() as conn:
                conn.execute(
                    "INSERT INTO users VALUES (?,?,?,?,?,?)",
                    (uid, username, password_hash, 1, int(system_admin), _now()),
                )
                conn.executemany(
                    "INSERT INTO memberships VALUES (?,?,?)",
                    [(uid, m.department, m.role) for m in memberships],
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateUserError from exc
        return uid

    def user_by_username(self, username):
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()

    def user_info(self, uid):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id,username,system_admin FROM users WHERE id=? AND active=1",
                (uid,),
            ).fetchone()
            if not row:
                return None
            memberships = conn.execute(
                "SELECT department,role FROM memberships WHERE user_id=? ORDER BY department",
                (uid,),
            ).fetchall()
            return {
                **dict(row),
                "system_admin": bool(row["system_admin"]),
                "memberships": [dict(m) for m in memberships],
            }

    def user_role(self, uid, department):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT role FROM memberships WHERE user_id=? AND department=?",
                (uid, department),
            ).fetchone()
            return row["role"] if row else None

    def user_members(self, department):
        with self.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT u.id,u.username,m.role FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.department=? AND u.active=1",
                    (department,),
                )
            ]

    def set_user_role(self, uid, department, role):
        with self.connect() as conn:
            if not conn.execute(
                "SELECT id FROM users WHERE id=? AND active=1", (uid,)
            ).fetchone():
                return False
            conn.execute(
                "INSERT INTO memberships VALUES (?,?,?) ON CONFLICT(user_id,department) DO UPDATE SET role=excluded.role",
                (uid, department, role),
            )
            return True

    def remove_user_role(self, uid, department):
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM memberships WHERE user_id=? AND department=?",
                (uid, department),
            )

    def create_session(self, token_hash, user_id, expires_at):
        with self.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at<=?", (time.time(),))
            conn.execute(
                "INSERT INTO sessions VALUES (?,?,?)",
                (token_hash, user_id, expires_at),
            )

    def authenticated_user(self, token_hash, now):
        with self.connect() as conn:
            return conn.execute(
                "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1",
                (token_hash, now),
            ).fetchone()

    def delete_session(self, token_hash):
        with self.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    def delete_user_sessions(self, user_id):
        with self.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))

    def record_audit(self, actor_id, department, action, target_id, timestamp):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO audit_events(actor_id,department,action,target_id,timestamp) VALUES (?,?,?,?,?)",
                (actor_id, department, action, target_id, timestamp),
            )

    def ensure_guest(self, guest_id, departments, timestamp):
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?)",
                (guest_id, "_development_guest", "!", 1, 0, timestamp),
            )
            conn.executemany(
                "INSERT OR IGNORE INTO memberships VALUES (?,?,?)",
                [(guest_id, department, "member") for department in departments],
            )

    def check_rate_limit(self, key, limit, now, window):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM rate_limits WHERE reset_at<=?", (now,))
            row = conn.execute(
                "SELECT * FROM rate_limits WHERE key=?", (key,)
            ).fetchone()
            if row and row["count"] >= limit:
                return max(1, int(row["reset_at"] - now + 0.999999))
            if row:
                conn.execute("UPDATE rate_limits SET count=count+1 WHERE key=?", (key,))
            else:
                conn.execute(
                    "INSERT INTO rate_limits VALUES (?,?,?)", (key, 1, now + window)
                )
        return None

    def append_turn(self, conversation, message):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conversation["is_new"]:
                conn.execute(
                    "INSERT INTO conversations(id,user_id,department,mode,preview,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        conversation["id"],
                        conversation["user_id"],
                        conversation["department"],
                        conversation["mode"],
                        conversation["preview"],
                        conversation["timestamp"],
                        conversation["timestamp"],
                    ),
                )
            else:
                row = conn.execute(
                    "SELECT mode FROM conversations WHERE id=? AND user_id=? AND department=?",
                    (
                        conversation["id"],
                        conversation["user_id"],
                        conversation["department"],
                    ),
                ).fetchone()
                if not row:
                    return "not_found"
                if row["mode"] != conversation["mode"]:
                    return "mode_conflict"
            conn.execute(
                "INSERT INTO messages(conversation_id,user_message,assistant_response,timestamp) VALUES (?,?,?,?)",
                (
                    conversation["id"],
                    message["user_message"],
                    message["assistant_response"],
                    message["timestamp"],
                ),
            )
            conn.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?",
                (conversation["timestamp"], conversation["id"]),
            )
        return "ok"

    def conversation(self, cid, user_id, department):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id=? AND user_id=? AND department=?",
                (cid, user_id, department),
            ).fetchone()
            return dict(row) if row else None

    def list_conversations(self, user_id, department, limit, offset):
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id,id AS conversation_id,mode,preview,created_at,updated_at FROM conversations WHERE user_id=? AND department=? ORDER BY updated_at DESC,id DESC LIMIT ? OFFSET ?",
                (user_id, department, limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]

    def conversation_messages(self, cid):
        with self.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT user_message,assistant_response,timestamp FROM messages WHERE conversation_id=? ORDER BY id",
                    (cid,),
                ).fetchall()
            ]

    def delete_conversation(self, cid):
        with self.connect() as conn:
            conn.execute("DELETE FROM conversations WHERE id=?", (cid,))

    def cleanup(self, now):
        with self.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            conn.execute("DELETE FROM rate_limits WHERE reset_at<=?", (now,))

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _now():
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
