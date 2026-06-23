#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
PYTHON="$ROOT_DIR/.venv/bin/python"
UVICORN="$ROOT_DIR/.venv/bin/uvicorn"
BACKEND_URL="http://127.0.0.1:8000/health"
FRONTEND_URL="http://127.0.0.1:5173/"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "$FRONTEND_PID" ]]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
  if [[ -n "$BACKEND_PID" ]]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

wait_for() {
  local url="$1"
  local label="$2"
  for _ in {1..40}; do
    if curl -fsS "$url" >/dev/null 2>&1; then return 0; fi
    sleep 0.25
  done
  echo "$label did not start: $url"
  return 1
}

cd "$ROOT_DIR"
export DATABASE_URL="${COGNOSOS_LAUNCHER_DATABASE_URL:-sqlite:///$ROOT_DIR/cognosos_demo.db}"
export COGNOSOS_LAUNCHER_PID="$$"

if [[ ! -x "$UVICORN" ]]; then
  echo "Missing backend runtime: $UVICORN"
  echo "Run: python -m venv .venv && source .venv/bin/activate && pip install -e '.[test]'"
  exit 1
fi

if ! curl -fsS "$BACKEND_URL" >/dev/null 2>&1; then
  echo "Starting CognosOS backend..."
  "$UVICORN" backend.app.main:app --host 127.0.0.1 --port 8000 &
  BACKEND_PID="$!"
  wait_for "$BACKEND_URL" "Backend"
else
  echo "Backend already running."
fi

if [[ ! -f "$FRONTEND_DIR/dist/index.html" ]]; then
  echo "Building frontend..."
  (cd "$FRONTEND_DIR" && npm install && npm run build)
fi

if ! curl -fsS "$FRONTEND_URL" >/dev/null 2>&1; then
  echo "Starting CognosOS frontend..."
  "$PYTHON" -m http.server 5173 --bind 127.0.0.1 --directory "$FRONTEND_DIR/dist" &
  FRONTEND_PID="$!"
  wait_for "$FRONTEND_URL" "Frontend"
else
  echo "Frontend already running."
fi

open "$FRONTEND_URL"

echo
echo "CognosOS is running at $FRONTEND_URL"
echo "Markdown vault is controlled by COGNOSOS_VAULT_PATH in .env."
echo "Close this window or press Ctrl-C to stop services started by this launcher."

while true; do sleep 3600; done
