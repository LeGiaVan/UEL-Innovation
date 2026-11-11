"""Check the isolated benchmark container's logs without printing their contents."""

import json
import re
import subprocess
from pathlib import Path

from app.core.config import Settings


def main():
    ids = subprocess.run(
        ["docker", "ps", "--filter", "publish=18080", "--format", "{{.ID}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if len(ids) != 1:
        raise RuntimeError("expected exactly one isolated benchmark container")
    logs = subprocess.run(["docker", "logs", ids[0]], check=True, capture_output=True)
    data = logs.stdout + logs.stderr
    settings = Settings()
    secrets = [
        settings.app_api_key.get_secret_value(),
        settings.llm_api_key.get_secret_value(),
        settings.postgres_password.get_secret_value(),
        settings.minio_secret_key.get_secret_value(),
    ]
    found = sum(bool(secret) and secret.encode() in data for secret in secrets)
    emails = len(re.findall(rb"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", data))
    report = {"secret_matches": found, "email_matches": emails, "log_bytes": len(data)}
    Path("reports/phases/phase-08-logs.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report))
    if found or emails:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
