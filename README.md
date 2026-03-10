# Matt

AI-assisted pipeline for turning structured spreadsheets into technical reports.

The project reads a workbook, extracts the relevant checklist items, stores the intake in SQLite,
enriches the analysis with link scraping, builds a compact context for an AI model, and returns a
report in `DOCX` or `PDF`.

## Why this project exists

Many teams work from spreadsheets that already contain the facts, statuses and notes required for a
report, but still need to rewrite everything manually into narrative form.

Matt automates that middle layer:

1. ingest the workbook;
2. normalize the relevant rows;
3. persist the intake and metadata;
4. enrich the context by scraping referenced pages;
5. review the extracted context before generation;
6. prepare a focused summary for AI generation;
7. assemble the final report in a reusable template.

## Core capabilities

- Workbook ingestion tuned to a real checklist layout.
- Rule-based report generation.
- Local AI generation with Ollama.
- Remote AI generation with OpenAI-compatible APIs.
- Link scraping with contextual classification.
- Link scraping with evidence scoring, matched terms, prioritized links and controlled-depth crawling.
- SQLite persistence for analyses, extracted items, scraped pages and summaries.
- `DOCX` generation with template preservation.
- `PDF` export for lightweight sharing.

## Architecture

```text
Web UI
  ->
FastAPI
  ->
Workbook parser
  ->
Analysis store (SQLite)
  ->
Link scraper
  ->
Context builder
  ->
AI provider or rule engine
  ->
Report composer
  ->
DOCX / PDF
```

## Current workbook model

The default parser is tuned to a workbook with:

- sheet `Checklist`;
- item code in column `B`;
- item description in column `C`;
- yearly answers in columns `R` and `S`;
- source reference in column `T`;
- rationale in column `U`;
- a trailing observations block, with item code in `B` and note text in `E`.

The current extraction scope is intentionally narrow:

- groups `1` and `5`;
- statuses `Nao` and `Parcialmente`;
- notes linked from the observations block.

That scope can be expanded later without changing the rest of the pipeline.

The parser is now configurable per request through:

- parser profiles such as `default`, `extended` and `full`;
- explicit group overrides;
- explicit status overrides;
- sheet name and metadata row overrides.

## End-to-end flow

### 1. Intake

The user uploads:

- a spreadsheet file;
- optional document metadata;
- an optional `DOCX` template;
- the desired output format;
- the preferred generation mode.

### 2. Persistence

The backend creates an analysis record in SQLite and stores:

- input metadata;
- extracted items;
- item details;
- parser warnings.

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

- extracted items;
- parser warnings;
- scraped pages and discovered links;
- consolidated summary;
- prompt preview.

### 5. AI-ready summary

After review, the backend builds a consolidated summary from the database, so the model receives only:

- the relevant extracted rows;
- the scraped context that matters;
- the metadata needed to draft the report.

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
    main.py
    models.py
    services/
      analysis_context_builder.py
      analysis_store.py
      excel_parser.py
      link_scraper.py
      openai_report_content_builder.py
      ollama_report_content_builder.py
      prompt_builder.py
      report_builder.py
      report_content_builder.py
      technical_report_composer.py
  data/
    matt.db
frontend/
  index.html
  app.js
  styles.css
docs/
scripts/
```

## Requirements

- Python `3.9+`
- `pip`
- optional: Ollama for local generation

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

Alternative:

```bash
uvicorn backend.app.main:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

If port `8000` is already in use:

```bash
pkill -f "uvicorn backend.app.main:app" || true
```

## Database

Analyses are stored in:

```text
backend/data/matt.db
```

The database currently keeps:

- analysis metadata;
- parser options used for each analysis;
- extracted checklist items;
- item-level detail rows;
- parser warnings;
- scraped pages;
- scraped links;
- consolidated AI summaries.
- generation audit trail with mode, provider, model, prompt snapshot and raw response.

## API overview

### Utility

- `GET /`
- `GET /health`
- `GET /parser/profiles`
- `GET /providers/ollama/models`
- `GET /scrape/links`

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
ollama pull qwen2.5:7b
export OLLAMA_MODEL="qwen2.5:7b"
export OLLAMA_TIMEOUT_SECONDS="600"
```

The backend uses `http://127.0.0.1:11434` by default.

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

- the parser is still tuned to one workbook family;
- the default extraction scope is narrow;
- link classification is heuristic;
- the AI layer receives curated context, not raw workbook dumps;
- generated `PDF` files do not preserve `DOCX` visual templates.

## Suggested roadmap

1. Expand parsing beyond the current row groups.
2. Add configurable workbook schemas.
3. Promote the scraper context into first-class evidence blocks.
4. Add review and approval states for persisted analyses.
5. Introduce automated regression samples for workbook-to-report conversion.

## Documentation

- [MVP scope](/Users/brunomartins/Desktop/Projetos/Mobile/Projetos/Matt%20/docs/escopo-mvp.md)
- [Workbook mapping](/Users/brunomartins/Desktop/Projetos/Mobile/Projetos/Matt%20/docs/mapeamento-planilha-relatorio.md)
- [Project overview](/Users/brunomartins/Desktop/Projetos/Mobile/Projetos/Matt%20/docs/projeto-e-mvp.md)
