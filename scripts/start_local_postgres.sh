#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.postgres.local.yml"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return
  fi
  return 1
}

COMPOSE_CMD="$(detect_compose || true)"
if [[ -z "$COMPOSE_CMD" ]]; then
  echo "Nenhum comando de compose foi encontrado. Instale Docker Desktop, Colima+Docker CLI ou docker-compose." >&2
  exit 1
fi

if [[ "$COMPOSE_CMD" == "docker compose" ]]; then
  if ! docker info >/dev/null 2>&1; then
    echo "O daemon do Docker nao esta acessivel. Inicie o Docker antes de subir o Postgres local." >&2
    exit 1
  fi
  docker compose -f "$COMPOSE_FILE" up -d
  docker compose -f "$COMPOSE_FILE" ps
  exit 0
fi

if ! docker-compose -f "$COMPOSE_FILE" ps >/dev/null 2>&1; then
  echo "O daemon do Docker nao esta acessivel. Inicie o Docker antes de subir o Postgres local." >&2
  exit 1
fi

docker-compose -f "$COMPOSE_FILE" up -d
docker-compose -f "$COMPOSE_FILE" ps
