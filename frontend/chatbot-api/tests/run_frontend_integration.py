"""Starts a temporary local backend; no project database or real accounts are used."""

import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from app.db.database import Database
from app.repositories.users import UserRepository
from app.schemas.api import Membership

ROOT = Path(__file__).resolve().parents[1]


def main():
    with TemporaryDirectory(prefix="chatbot-integration-") as temp:
        db = Database(Path(temp) / "test.sqlite3")
        db.initialize()
        password = secrets.token_urlsafe(24)
        UserRepository(db).create(
            "integration",
            password,
            [
                Membership(department=d)
                for d in ["dbcl", "qtts", "pdt", "pns", "hc", "ctsv"]
            ],
        )
        env = {
            **os.environ,
            "CHATBOT_DATABASE_BACKEND": "sqlite",
            "CHATBOT_DATABASE_PATH": str(db.path),
            "CHATBOT_ENVIRONMENT": "test",
            "CHATBOT_AUTH_DISABLED": "false",
        }
        port = 30958
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
                "--no-proxy-headers",
                "--log-level",
                "error",
            ],
            cwd=ROOT,
            env=env,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Temporary API failed to start")
                try:
                    if (
                        httpx.get(f"http://127.0.0.1:{port}/health/ready").status_code
                        == 200
                    ):
                        break
                except httpx.ConnectError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Temporary API did not become ready")
            for suffix in ["DBCL", "qtts", "PDT", "PNS", "HC", "CTSV"]:
                frontend = ROOT.parent / f"chatbot-{suffix}"
                node_env = {
                    **os.environ,
                    "FRONTEND_ROOT": str(frontend),
                    "TEST_PASSWORD": password,
                    "VITE_API_URL": f"http://127.0.0.1:{port}/api",
                    "VITE_MOCK_API": "false",
                }
                subprocess.run(
                    ["node", str(ROOT / "tests/frontend-live.mjs")],
                    cwd=frontend,
                    env=node_env,
                    check=True,
                )
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
