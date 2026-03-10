#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

cd "$ROOT_DIR"

if [[ "${SKIP_PORT_CLEANUP:-0}" != "1" ]]; then
  PIDS=()
  while IFS= read -r pid; do
    [[ -n "$pid" ]] && PIDS+=("$pid")
  done < <(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)

  if (( ${#PIDS[@]} > 0 )); then
    echo "Liberando porta $PORT: ${PIDS[*]}"
    kill "${PIDS[@]}" 2>/dev/null || true
    sleep 1

    REMAINING_PIDS=()
    while IFS= read -r pid; do
      [[ -n "$pid" ]] && REMAINING_PIDS+=("$pid")
    done < <(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)

    if (( ${#REMAINING_PIDS[@]} > 0 )); then
      echo "Forcando encerramento na porta $PORT: ${REMAINING_PIDS[*]}"
      kill -9 "${REMAINING_PIDS[@]}" 2>/dev/null || true
    fi
  fi
fi

exec "$ROOT_DIR/.venv/bin/uvicorn" backend.app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --reload \
  --reload-dir "$ROOT_DIR/backend" \
  --reload-dir "$ROOT_DIR/frontend"
