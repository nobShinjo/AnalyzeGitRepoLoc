# Change: Update plot auto-display behavior

## Why

Multi-repository runs currently auto-open every Plotly chart, which is noisy.
The desired behavior is to suppress all auto-open when --no-plot-show is set,
keep single-repository chart auto-open when allowed, and open only
eport.html
for multi-repository runs.

## What Changes

- When --no-plot-show is set, skip all interactive chart/report auto-open.
- For single-repository analysis and --no-plot-show not set, keep auto-opening
  Language/Author charts.
- For multi-repository analysis and --no-plot-show not set, open
eport.html
  and do not auto-open any Plotly charts.

## Impact

- Affected specs: outputs
- Affected code: analyze_git_repo_loc/__main__.py, analyze_git_repo_loc/html_report.py
