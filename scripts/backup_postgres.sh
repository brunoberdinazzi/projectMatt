#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

APP_DATABASE_URL="${DATABASE_URL:-}"
FINANCE_DATABASE_URL="${FINANCE_DATABASE_URL:-}"
BACKUP_DIR="${POSTGRES_BACKUP_DIR:-$ROOT_DIR/.backups}"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
REQUIRE_ENCRYPTION="${BACKUP_REQUIRE_ENCRYPTION:-0}"
BACKUP_PASSPHRASE="${BACKUP_PASSPHRASE:-}"

if [[ -z "$APP_DATABASE_URL" ]]; then
  echo "DATABASE_URL nao definido. Ajuste o .env antes de rodar o backup." >&2
  exit 1
fi

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "pg_dump nao encontrado. Instale o cliente do PostgreSQL antes de rodar o backup." >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

encrypt_dump() {
  local source_file="$1"
  local target_file="${source_file}.enc"

  if [[ -z "$BACKUP_PASSPHRASE" ]]; then
    if [[ "$REQUIRE_ENCRYPTION" == "1" ]]; then
      echo "BACKUP_REQUIRE_ENCRYPTION=1, mas BACKUP_PASSPHRASE nao foi definido." >&2
      exit 1
    fi
    echo "Backup gerado sem criptografia adicional: $source_file"
    return
  fi

  if ! command -v openssl >/dev/null 2>&1; then
    echo "openssl nao encontrado. Nao foi possivel criptografar o dump." >&2
    exit 1
  fi

  openssl enc -aes-256-cbc -pbkdf2 -salt \
    -in "$source_file" \
    -out "$target_file" \
    -pass env:BACKUP_PASSPHRASE >/dev/null 2>&1

  rm -f "$source_file"
  echo "Backup criptografado gerado em: $target_file"
}

dump_database() {
  local label="$1"
  local database_url="$2"
  local output_file="$BACKUP_DIR/${label}_${TIMESTAMP}.dump"

  echo "Gerando dump de $label..."
  pg_dump --format=custom --no-owner --no-privileges --file "$output_file" "$database_url"
  encrypt_dump "$output_file"
}

dump_database "app" "$APP_DATABASE_URL"

if [[ -n "$FINANCE_DATABASE_URL" && "$FINANCE_DATABASE_URL" != "$APP_DATABASE_URL" ]]; then
  dump_database "finance" "$FINANCE_DATABASE_URL"
fi
