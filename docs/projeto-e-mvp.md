# Project Overview and MVP

## What Draux Inc. is

Draux Inc. is a practical pipeline for converting structured spreadsheet data into report-ready text with
AI assistance.

It combines:

- workbook parsing;
- contextual link scraping;
- local persistence;
- focused AI prompting;
- report assembly.

## Product idea

The core product idea is simple:

1. users already capture facts in spreadsheets;
2. those facts already contain statuses, notes and references;
3. the expensive part is rewriting them into a coherent report;
4. the system should automate that rewrite without losing traceability.

## What makes the approach useful

Instead of sending raw spreadsheets directly to a model, Draux Inc. builds a controlled pipeline:

- parse first;
- normalize second;
- persist third;
- enrich context fourth;
- ask the model only for the narrative layer.

This keeps the AI focused on writing, not on reverse-engineering workbook layout.

## Current implementation status

The project already includes:

- a web UI for uploads and generation;
- a parser for the sample workbook layout;
- SQLite persistence;
- a scraper for page links and their local context;
- context summaries built from the database;
- local and remote AI adapters;
- rule-based fallback generation;
- `DOCX` and `PDF` export.

## MVP definition

The MVP is not meant to solve every workbook family.

It is meant to prove four things:

1. spreadsheet input can be normalized reliably;
2. AI can receive only the relevant subset of data;
3. the report can be generated in a repeatable structure;
4. every step can remain auditable in a database.

## Minimal user journey

1. upload workbook and metadata;
2. persist the intake;
3. enrich the analysis by scraping the referenced pages;
4. build a condensed AI context;
5. generate the report with AI or deterministic rules;
6. export the file and keep the analysis record.

## Why persistence matters

Without persistence, the pipeline is opaque.

With persistence, each analysis has:

- a stable identifier;
- reusable input metadata;
- extracted rows;
- scraped context;
- a stored AI summary;
- a reproducible output path.

That makes the system easier to debug, review and extend.

## AI strategy

Draux Inc. supports multiple generation paths:

- deterministic local rules;
- local models through Ollama;
- remote models through OpenAI-compatible APIs.

The important design choice is that the model does not fetch raw data directly. The backend retrieves
and curates the context first.

## Recommended next step

The smartest next step after this MVP is to broaden parsing coverage and strengthen regression
fixtures, so the project can support more workbook variations without sacrificing consistency.
