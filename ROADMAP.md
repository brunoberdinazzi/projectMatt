# Roadmap

This roadmap starts from the current state of the project:

- workbook ingestion is working for the current sample layout;
- analyses are persisted in SQLite;
- link scraping is available;
- AI context is built from stored data;
- report generation already supports `DOCX` and `PDF`.

The next versions should focus less on "more AI" and more on reliability, reviewability and
coverage.

## v0.2

### Goal

Turn the current proof of concept into a dependable internal workflow.

### Focus

- stronger parsing;
- review before generation;
- better observability of what the AI receives.

### Deliverables

1. Configurable parsing scope
   - allow enabling groups beyond `1` and `5`;
   - support profile-based parsing rules;
   - separate parser configuration from parser logic.

2. Review screen before report generation
   - show extracted items;
   - show parser warnings;
   - show scraped pages and relevant links;
   - allow approving the AI context before generation.

3. Stored AI audit trail
   - save generation mode;
   - save model used;
   - save prompt snapshot;
   - save raw model response;
   - save generation timestamp.

4. Regression tests for parsing
   - fixtures for representative workbooks;
   - tests for item extraction;
   - tests for note linking;
   - tests for status normalization.

### Definition of done

- the same workbook generates the same structured analysis in repeated runs;
- users can inspect the context before generating the report;
- each generated report can be traced back to prompt, model and stored analysis.

### Main risk

The parser remains too coupled to one workbook family.

## v0.3

### Goal

Improve evidence quality and reduce heuristic guesswork.

### Focus

- better scraper evidence;
- stronger data model;
- better report composition fidelity.

### Deliverables

1. Multi-step scraping
   - controlled depth crawling for relevant links;
   - scoring and prioritization of discovered pages;
   - capture of page snippets, not only links;
   - deduplication across pages and categories.

2. Evidence-oriented database model
   - explicit entities for findings, sources and evidence;
   - link findings to scraped evidence;
   - mark evidence quality or confidence;
   - preserve source-to-report traceability.

3. Structured report blocks
   - split report generation into reusable sections;
   - improve template insertion rules;
   - allow swapping document templates without rewriting the pipeline.

4. Better evaluation tooling
   - sample analyses with expected outputs;
   - diff-friendly snapshots for generated sections;
   - quality checks for empty or generic outputs.

### Definition of done

- scraper output contributes usable evidence, not only navigation hints;
- persisted records explain why a given paragraph exists;
- report blocks are reusable and independently testable.

### Main risk

Scraping can add noise faster than it adds value if ranking is weak.

## v1.0

### Goal

Ship a stable, reviewable and extensible spreadsheet-to-report platform.

### Focus

- reliability;
- maintainability;
- publishing quality.

### Deliverables

1. Configurable intake layer
   - multiple workbook schemas;
   - versioned parsing profiles;
   - validation feedback for unsupported files.

2. End-to-end review workflow
   - analysis status lifecycle;
   - draft, reviewed and exported states;
   - analyst comments and corrections.

3. Production-grade persistence
   - schema migration strategy;
   - database backup policy;
   - exportable analysis bundles.

4. Stable public documentation
   - architecture guide;
   - contribution guide;
   - sample workflows;
   - release notes process.

5. Release-quality testing
   - parser tests;
   - store tests;
   - scraper tests;
   - report generation tests;
   - smoke tests for local and remote AI providers.

### Definition of done

- the system supports more than one real workbook profile;
- every report is reproducible from stored analysis data;
- the project can be handed to another developer without hidden knowledge.

### Main risk

Feature growth outpaces the effort spent on schema discipline and tests.

## Cross-version priorities

These priorities should remain active across all versions:

1. Preserve traceability between workbook, evidence, prompt and report.
2. Keep AI responsible for wording, not for reconstructing facts.
3. Prefer explicit data structures over hidden prompt conventions.
4. Expand coverage only when regression fixtures exist.

## Suggested implementation order

If development happens incrementally, the best sequence is:

1. parser configurability;
2. analysis review UI;
3. prompt and response persistence;
4. stronger scraper evidence capture;
5. normalized evidence model;
6. broader workbook support;
7. workflow status and approval layer.
