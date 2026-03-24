# Deploy seguro com PostgreSQL no Debian

Este projeto já roda localmente com SQLite ou PostgreSQL. Para preparar a migração para um servidor Debian pequeno, siga este caminho:

## 1. Ambiente

- mantenha o app e o PostgreSQL na mesma máquina ou em rede privada;
- use volume persistente para o banco;
- mantenha o disco/volume criptografado no host;
- use `DRAUX_DATA_KEY` externo e estável.

## 2. Variáveis

Copie o arquivo base:

```bash
cp .env.example .env
```

Ajuste pelo menos:

- `DATABASE_URL`
- `FINANCE_DATABASE_URL` se o warehouse ficar separado
- `DRAUX_DATA_KEY`
- `DRAUX_TRUSTED_ORIGINS`
- `AUTH_COOKIE_SECURE=true`
- `DRAUX_STRICT_SECURITY_PREFLIGHT=1`

Para PostgreSQL remoto, prefira:

```text
postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
```

## 3. PostgreSQL local via Docker

Para levantar um Postgres local preso ao loopback:

```bash
./scripts/start_local_postgres.sh
```

Esse compose foi pensado para desenvolvimento e homologação local. Ele expõe a porta só em `127.0.0.1`.

## 4. Rodando o app

O script de desenvolvimento agora pode carregar automaticamente as variáveis do `.env`:

```bash
./scripts/run_dev.sh
```

## 5. Backups

O projeto inclui um helper para dump customizado:

```bash
./scripts/backup_postgres.sh
```

Se `BACKUP_PASSPHRASE` estiver definido, o dump sai criptografado com `openssl`.
Se quiser tornar isso obrigatório:

```bash
export BACKUP_REQUIRE_ENCRYPTION=1
```

## 6. Checklist antes de sair do Mac

- migrar os dados atuais com `scripts/migrate_sqlite_to_postgres.py`;
- validar `run_security_preflight()` sem warnings críticos;
- confirmar restauração de backup;
- manter `DRAUX_DATA_KEY` fora do repositório;
- revisar `DRAUX_TRUSTED_ORIGINS` com a origem real do frontend;
- subir com `AUTH_COOKIE_SECURE=true`.
