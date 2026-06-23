#!/bin/zsh
set -euo pipefail

stop_port() {
  local port="$1"
  local label="$2"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    echo "$label is not running."
    return
  fi
  for pid in ${(f)pids}; do
    kill "$pid" 2>/dev/null || true
  done
  echo "Stopped $label."
}

stop_port 5173 "CognosOS frontend"
stop_port 8000 "CognosOS backend"

echo "CognosOS stopped. You can close this window."
