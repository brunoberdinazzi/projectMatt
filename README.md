# Draux Inc.

AI-assisted workspace for turning structured spreadsheets and financial statements into technical
and executive reports.

The project can ingest checklist workbooks, financial control sheets, `.xlsm` files and bank
statement PDFs, review the extracted structure in a web UI, persist the analysis in SQLite or
PostgreSQL, and generate reports in `DOCX` or `PDF` using rules, local Ollama models or a remote
OpenAI-compatible provider.

## Why this project exists

Many teams already keep the facts in spreadsheets, but still lose time rewriting them into reports,
manual summaries or financial statements.

Draux automates that middle layer:

1. detect the input profile automatically;
2. normalize rows, periods, clients, contracts and evidence;
3. persist the intake and the derived structure;
4. enrich the analysis with scraping when relevant;
5. review the structured output before generation;
6. assemble a deterministic or AI-assisted report;
7. keep traceability in the database for reopening and audit.

## Core capabilities

- Automatic parser detection between checklist and financial DRE flows.
- Checklist parsing with multi-sheet context layers and referenced links.
- Financial parsing from `.xlsx`, `.xlsm` and bank statement `PDF`.
- Multi-file DRE consolidation with client, contract and period rollups.
- Canonical financial warehouse in SQLite or PostgreSQL.
- Traceability view for financial entries, reconciliation and prompt history.
- Rule-based report generation.
- Local AI generation with Ollama, optimized for `deepseek-r1:8b`.
- Remote AI generation with OpenAI-compatible APIs.
- Link scraping with SSRF guard, classification, evidence scoring and controlled-depth crawling.
- Authenticated workspace with saved analyses and generation history.
- `DOCX` generation with template preservation.
- `PDF` export for lightweight sharing.

## Architecture

```text
Web UI
  ->
FastAPI
  ->
Parser detection
  ->
Checklist / financial parsers
  ->
Operational store (SQLite or PostgreSQL)
  ->
Canonical financial warehouse
  ->
Review and traceability layer
  ->
AI provider or rule engine
  ->
DOCX / PDF
```

## Supported analysis modes

### Checklist / extended review

The checklist flow still supports the narrow workbook family that originated the project, but it now
also handles:

- parser profiles such as `default`, `extended`, `full` and `auto`;
- multi-sheet checklist ingestion;
- workbook context layers for heterogeneous sheets;
- review with items, warnings, prompt preview and scraping evidence.

### Financial / DRE

The financial flow now supports:

- monthly control spreadsheets in `.xlsx`;
- richer `.xlsm` control workbooks;
- multi-file DRE consolidation in one run;
- bank statement `PDF` ingestion for reconciliation;
- rollups by client, contract and period;
- canonical aliases and warehouse-backed traceability.

## End-to-end flow

### 1. Intake

The user uploads:

- one or more spreadsheet files;
- optional bank statement PDFs in the financial flow;
- optional document metadata;
- an optional `DOCX` template;
- the desired output format;
- the preferred generation mode or lets the parser stay in `auto`.

### 2. Persistence

The backend creates an analysis record in the configured database and stores:

- input metadata;
- extracted items or financial structures;
- parser warnings;
- prompt-ready summaries;
- generation audit trail.

### 3. Context enrichment

If source URLs are available, the backend scrapes those pages and stores:

- page title;
- final URL after redirects;
- categorized links;
- evidence score and matched terms for each relevant link;
- discovered pages reached through high-value links;
- surrounding context for each link;
- a compact page summary.

### 4. Review

Before generating the report, the UI can request an analysis review payload showing:

- extracted items or DRE structures;
- parser warnings;
- scraped pages and discovered links;
- consolidated summary and traceability;
- prompt preview.

### 5. AI-ready summary

After review, the backend builds a consolidated summary from the database, so the model receives only:

- the relevant extracted rows;
- the scraped context that matters;
- the metadata needed to draft the report;
- for financial reports, the database-backed client, contract and period facts.

The AI does not query the database directly. The backend retrieves and condenses the required
context first.

### 6. Report generation

The report can be produced by:

- `rules`: deterministic local generation;
- `local`: Ollama;
- `ai`: OpenAI-compatible API;
- `auto`: tries local, then remote, then rules.

## Repository structure

```text
backend/
  app/
    api/
    main.py
    models.py
    runtime.py
    services/
      analysis_workflow_service.py
      analysis_report_service.py
      excel_parser.py
      financial_workbook_parser.py
      bank_statement_parser.py
      financial_warehouse_store.py
      link_scraper.py
      openai_report_content_builder.py
      ollama_report_content_builder.py
      report_builder.py
  data/
frontend/
  src/
    App.tsx
    components/
    lib/
    types/
  index.html
docs/
scripts/
```

## Requirements

- Python `3.9+`
- Node `18+`
- `pip`
- optional: Ollama for local generation
- optional: Docker/Colima for local PostgreSQL

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running locally

Preferred development command:

```bash
./scripts/run_dev.sh
```

That script:

- loads `.env` automatically when present;
- builds the frontend;
- clears stale `uvicorn` processes on port `8000`;
- starts the backend in reload mode.

Alternative:

```bash
uvicorn backend.app.main:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

If port `8000` is already in use:

```bash
pkill -f "uvicorn backend.app.main:app" || true
```

The local runner now loads variables from `.env` automatically when the file exists.
Start from:

```bash
cp .env.example .env
```

If you use Colima instead of Docker Desktop, the local PostgreSQL path is:

```bash
colima start --cpu 2 --memory 4 --disk 20
./scripts/start_local_postgres.sh
./scripts/run_dev.sh
```

## Database

By default, analyses are stored in:

```text
backend/data/matt.db
```

To use PostgreSQL instead, configure:

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"
```

The canonical financial warehouse can share the same database or use a dedicated one:

```bash
export FINANCE_DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"
```

If `FINANCE_DATABASE_URL` is omitted, the app falls back to `DATABASE_URL`.

For PostgreSQL, the backend now normalizes connection URLs and automatically appends
`sslmode=require` when the target is not `localhost`. For local-only development on a loopback
database, the URL may stay without TLS. If you need an explicit override, use:

```bash
export DRAUX_DB_SSLMODE="require"
```

For local-only troubleshooting with a trusted loopback database, you can still force:

```bash
export DRAUX_DB_SSLMODE="disable"
```

The startup preflight can be made strict with:

```bash
export DRAUX_STRICT_SECURITY_PREFLIGHT="1"
```

For local PostgreSQL on loopback, the repository now also includes:

```bash
./scripts/start_local_postgres.sh
```

### Migrating SQLite to PostgreSQL

The repository now includes a migrator for:

- auth users and sessions;
- analyses and extracted structures;
- scrape history;
- generation history;
- financial warehouse snapshots.

Example:

```bash
./.venv/bin/python scripts/migrate_sqlite_to_postgres.py \
  --source-app-db backend/data/matt.db \
  --source-finance-db backend/data/draux_finance.db \
  --database-url "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require" \
  --truncate-existing
```

### PostgreSQL security checklist

For anything beyond localhost, prefer this baseline:

- use `sslmode=require` or `sslmode=verify-full` in `DATABASE_URL` and `FINANCE_DATABASE_URL`;
- keep `AUTH_COOKIE_SECURE=true` outside localhost;
- define `DRAUX_TRUSTED_ORIGINS` with your frontend origin list;
- set a stable external `DRAUX_DATA_KEY` instead of relying on `backend/data/.draux_master_key`;
- place PostgreSQL on an encrypted disk/volume;
- keep database dumps and snapshots encrypted at rest;
- if you enable strict startup checks, use `DRAUX_STRICT_SECURITY_PREFLIGHT=1`.

### Operational helpers

The repository now includes:

- `.env.example` for local and deployment-ready environment variables;
- `docker-compose.postgres.local.yml` for loopback-only PostgreSQL;
- `scripts/start_local_postgres.sh` to detect `docker compose`/`docker-compose` and start the local PostgreSQL service;
- `scripts/backup_postgres.sh` for dumps in custom format, with optional OpenSSL encryption;
- `docs/deploy-postgres-debian.md` with a step-by-step path for moving from the Mac to a Debian host.

### Financial analytical views

The canonical warehouse now exposes SQL views for direct querying:

- `finance_client_revenue_view`
- `finance_contract_revenue_view`
- `finance_period_result_view`

These views are useful for:

- top clients by revenue in the selected analysis;
- top contracts by accumulated yield;
- best and worst periods by net result;
- dashboards and deterministic report sections without relying on AI for the numbers.

The database currently keeps:

- analysis metadata;
- parser options used for each analysis;
- extracted checklist items;
- financial snapshots, periods, clients, contracts and trace entries;
- item-level detail rows;
- parser warnings;
- scraped pages;
- scraped links;
- consolidated AI summaries;
- generation audit trail with mode, provider, model, prompt snapshot and raw response.

## API overview

### Utility

- `GET /`
- `GET /health`
- `GET /parser/profiles`
- `POST /parser/detect`
- `GET /providers/ollama/models`
- `GET /providers/ollama/status`
- `GET /scrape/links`

### Auth

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `PUT /auth/profile`
- `POST /auth/password`

The scraper endpoint also accepts:

- `crawl_depth`
- `max_pages`

### Intake and persistence

- `POST /analysis/intake`
- `POST /analysis/review`
- `GET /analysis/{analysis_id}`
- `POST /analysis/{analysis_id}/scrape`
- `GET /analysis/{analysis_id}/context`
- `GET /analysis/{analysis_id}/generations`
- `POST /analysis/{analysis_id}/report`

### Workbook and report pipeline

- `POST /checklist/upload`
- `POST /prompt/build`
- `POST /pipeline/run`
- `POST /report/build`
- `POST /report/generate`

When using `POST /report/generate`, the response also includes:

```text
X-Analysis-ID
```

That header identifies the persisted record associated with the generated report.

The two-step workflow exposed in the frontend is now:

1. upload and review with `POST /analysis/review`;
2. generate from the stored analysis with `POST /analysis/{analysis_id}/report`.

## Link scraper

The built-in scraper helps enrich the analysis before AI generation.

Example:

```bash
curl "http://127.0.0.1:8000/scrape/links?url=https://example.com&max_links=20"
```

The scraper returns:

- requested URL;
- final URL;
- page title;
- summary;
- extracted links;
- inferred category for each link;
- local context around each link.

Typical categories include:

- `portal_transparencia`
- `esic`
- `licitacoes`
- `contratos`
- `obras`
- `institucional`
- `outros`

These categories are heuristics. They are meant to guide report generation, not to act as
authoritative labels.

## AI providers

### Local generation with Ollama

Example setup:

```bash
ollama pull deepseek-r1:8b
export OLLAMA_MODEL="deepseek-r1:8b"
export OLLAMA_TIMEOUT_SECONDS="600"
```

The backend uses `http://127.0.0.1:11434` by default.
When `OLLAMA_MODEL` is not set, the backend now prefers `deepseek-r1:8b` automatically if it is installed.
The UI also consumes `/providers/ollama/status` to show latency, loaded model and local availability before generation.

### Remote generation with OpenAI-compatible APIs

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="gpt-4.1-mini"
```

Use environment variables or a local `.env` strategy. Do not hardcode secrets.

## Report output

### DOCX

If a template is uploaded, the final `DOCX` preserves:

- header;
- footer;
- page setup;
- embedded branding;
- Word styles.

You can also define a default template:

```bash
export REPORT_TEMPLATE_PATH="/path/to/template.docx"
```

### PDF

`PDF` output uses the built-in renderer and does not mirror the original `DOCX` template layout.

## Status and limitations

Current limitations are explicit:

- reconciliation between spreadsheet and bank statement is still conservative by design;
- some financial naming still depends on source workbook quality;
- link classification is heuristic;
- the AI layer receives curated context, not raw workbook dumps;
- generated `PDF` files do not preserve `DOCX` visual templates.

## Suggested roadmap

1. Promote the financial warehouse to the primary source for more report sections.
2. Improve reconciliation accuracy with stronger alias and counterparty rules.
3. Add automated regression suites for parser, warehouse and report generation.
4. Finish the TypeScript migration of the remaining frontend components.
5. Add deployment recipes for the Debian/PostgreSQL target.

## Documentation

- [MVP scope](docs/escopo-mvp.md)
- [Workbook mapping](docs/mapeamento-planilha-relatorio.md)
- [Project overview](docs/projeto-e-mvp.md)
- [PostgreSQL deploy guide](docs/deploy-postgres-debian.md)
