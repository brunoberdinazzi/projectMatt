# MVP Scope

## Goal

Build a usable first version of a spreadsheet-to-report pipeline with AI assistance.

The MVP should prove that a structured workbook can be transformed into a consistent report without
manual rewriting of every finding.

## What the MVP must do

1. accept a workbook upload;
2. extract the relevant rows from the configured checklist scope;
3. normalize statuses, notes and sources;
4. persist the intake in a local database;
5. optionally enrich the analysis with scraped links;
6. generate report text with rules or AI;
7. export the result as `DOCX` or `PDF`.

## In scope

- workbook parsing;
- narrow base extraction scope for predictable results, with room for broader profiles;
- metadata form ingestion;
- SQLite persistence;
- link scraping for contextual enrichment;
- AI-ready context building;
- local and remote AI adapters;
- `DOCX` generation with template support.

## Out of scope

- fully configurable workbook schemas;
- multi-tenant authentication;
- approval workflows;
- collaborative editing;
- advanced legal or domain inference;
- direct model access to the database.

## Expected input

The MVP assumes a workbook with:

- a main checklist sheet;
- row codes;
- descriptions;
- status columns;
- source reference;
- note or observations block.

It also accepts optional metadata such as:

- document number;
- requester or team;
- reference ID;
- issue date;
- collection period;
- supporting reference documents.

## Expected output

The system should return:

- a normalized analysis record;
- a persisted database entry;
- an AI context summary;
- a generated report file.

## MVP data flow

```text
Upload
  ->
Parse
  ->
Persist
  ->
Scrape
  ->
Summarize for AI
  ->
Generate report
  ->
Export
```

## Quality bar

The MVP is considered successful if it can:

- process a real workbook sample end to end;
- preserve key findings and notes;
- avoid inventing unsupported facts;
- generate a structured report repeatedly;
- keep every analysis traceable through the database.

## Risks

- workbook layouts may drift over time;
- source URLs may be absent or hard to detect;
- scraped links may be noisy;
- small local models may underperform on longer prompts;
- template-driven `DOCX` output may require iterative refinement.

## Next logical step after MVP

After the MVP is stable, the next expansion should be:

1. broader workbook coverage;
2. better link discovery;
3. stronger AI context filtering;
4. review states on persisted analyses;
5. regression fixtures for workbook parsing and report output.
