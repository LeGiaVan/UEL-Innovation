#!/bin/sh
set -eu
cd "$(dirname "$0")"
# Prefer the activated environment; otherwise use the project virtualenv.
if [ -n "${VIRTUAL_ENV:-}" ]; then
  chatbot_python="$VIRTUAL_ENV/bin/python"
else
  chatbot_python="$PWD/.venv/bin/python"
fi
"$chatbot_python" -c 'import argon2; from app.main import app' || {
  echo 'Install dependencies in the selected environment: python -m pip install -r requirements.lock' >&2
  exit 1
}
exec "$chatbot_python" -m uvicorn app.main:app --host 127.0.0.1 --port 30957 --reload --reload-dir app --no-proxy-headers --no-access-log
