# Change: Add interactive report filters

## Why

Interactive filtering improves exploratory analysis by letting users focus on specific languages, authors, or repositories inside the report.

## What Changes

- Add interactive filters in the HTML report for language, author, and repository.
- Update report charts/tables to respond to filter selections.

## Impact

- Affected specs: report-filters
- Affected code: HTML report generation, embedded data model, client-side filtering logic

## Dependencies

- Depends on change: add-html-report
