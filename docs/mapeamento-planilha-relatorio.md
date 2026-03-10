# Workbook to Report Mapping

## Purpose

This document explains how the current parser turns workbook rows into report-ready data.

It is intentionally generic, so the repository can be understood without the original sector-specific
background of the source files.

## Workbook assumptions

The parser currently expects:

- one main sheet named `Checklist`;
- item codes in column `B`;
- descriptions in column `C`;
- yearly status columns in `R` and `S`;
- source reference in `T`;
- rationale in `U`;
- a trailing observations block with item code in `B` and note text in `E`.

## Normalization rules

### Status selection

The parser selects the most recent applicable status:

1. prefer the rightmost year column with a value;
2. ignore `N/A`;
3. normalize variants such as `NAO`, `NÃO`, `PARCIAL`, `PARCIALMENTE`.

### Scope filter

The current default filter keeps only:

- groups `1` and `5`;
- rows marked as `Nao` or `Parcialmente`.

### Notes linkage

Notes from the observations block are linked back to the row code and then attached to the parsed
item as narrative guidance.

## Intermediate data model

Each relevant row becomes a structured record with:

- group;
- item code;
- row number;
- chosen year;
- normalized status;
- source key;
- original source text;
- item description;
- linked note;
- rationale;
- sub-item details, when present.

## Source mapping

Source text from the workbook is mapped to a normalized key:

- `site_orgao`
- `portal_transparencia`
- `esic`
- `nao_informada`

These keys are used consistently by:

- the report builders;
- the scraper;
- the database;
- the AI prompts.

## Report composition

The extracted records are later transformed into:

- results sections;
- recommendation sections;
- question summary;
- conclusion.

The system does not need the AI to understand the workbook layout directly. The backend transforms
the workbook into a much smaller, cleaner structure first.

## Database alignment

The persisted analysis keeps the mapping traceable:

- analysis metadata;
- extracted rows;
- item details;
- parser warnings;
- scraped pages;
- scraped links;
- consolidated summary for AI.

## Why this matters

A stable mapping layer keeps the rest of the pipeline replaceable.

That means you can evolve:

- the workbook layout;
- the AI provider;
- the report template;
- the scraper logic;

without redesigning the entire application.
