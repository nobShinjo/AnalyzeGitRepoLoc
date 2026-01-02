# Change: Add interactive report filters

## Why

Interactive filtering improves exploratory analysis by letting users focus on specific languages, authors, or repositories inside the report.

## What Changes

- Replace the filter panel with per-table tag filters for language, author, and repository.
- Apply filters to tables only and keep charts unchanged.
- Add tag search, default-enabled tags, and updated click behavior (all-enabled click selects only that tag; active tags are ignored when some are disabled; "x" disables).
- Add a Sum row to language tables with visual emphasis and keep title/tabs visible while cards scroll.

## Impact

- Affected specs: report-filters
- Affected code: HTML report generation, embedded data model, client-side filtering logic

## Dependencies

- Depends on change: add-html-report
