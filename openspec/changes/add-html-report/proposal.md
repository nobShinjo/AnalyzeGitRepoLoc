# Change: Add single HTML report

## Why

A consolidated HTML report improves sharing and review by bundling overview and per-repository results.

## What Changes

- Generate a single HTML report per run.
- Provide tabbed navigation for overall summary and per-repository details.
- Use the Tabler OSS template for the report layout and styling.
- Bundle Tabler CSS/JS assets with the report output (no CDN dependency).
- Embed Plotly charts inline in the report.
- Use Tabler tabs, tables, and cards for report structure.

## Impact

- Affected specs: html-report
- Affected code: report generation pipeline, HTML templating/layout, output packaging

## Decisions

- Adopt the Tabler OSS template (v1.4.0 or later) for the HTML report UI.
- Output format: `report.html` plus an `assets/` directory containing Tabler CSS/JS.
- Side navigation is out of scope for the initial release.
