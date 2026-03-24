#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
UVICORN_MATCH="$ROOT_DIR/.venv/bin/uvicorn backend.app.main:app"

cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

collect_server_pids() {
  local matched=()
  local pid

  while IFS= read -r pid; do
    [[ -n "$pid" ]] || continue
    matched+=("$pid")
  done < <(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)

  while IFS= read -r pid; do
    [[ -n "$pid" ]] || continue
    [[ "$pid" == "$$" ]] && continue
    if [[ " ${matched[*]-} " != *" $pid "* ]]; then
      matched+=("$pid")
    fi
  done < <(pgrep -f "$UVICORN_MATCH" 2>/dev/null || true)

  if (( ${#matched[@]} > 0 )); then
    printf '%s\n' "${matched[@]}"
  fi
}

if [[ -f "$ROOT_DIR/frontend/package.json" ]]; then
  if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
    echo "Instalando dependencias do frontend..."
    npm --prefix "$ROOT_DIR/frontend" install
  fi
  echo "Gerando build do frontend..."
  npm --prefix "$ROOT_DIR/frontend" run build >/dev/null
fi

if [[ "${SKIP_PORT_CLEANUP:-0}" != "1" ]]; then
  PIDS=()
  while IFS= read -r pid; do
    [[ -n "$pid" ]] && PIDS+=("$pid")
  done < <(collect_server_pids)

  if (( ${#PIDS[@]} > 0 )); then
    echo "Liberando porta $PORT: ${PIDS[*]}"
    kill "${PIDS[@]}" 2>/dev/null || true
    sleep 1

    REMAINING_PIDS=()
    while IFS= read -r pid; do
      [[ -n "$pid" ]] && REMAINING_PIDS+=("$pid")
    done < <(collect_server_pids)

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
