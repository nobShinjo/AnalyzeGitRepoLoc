# Tasks: Update plot auto-display behavior

## 1. Implementation

- [x] 1.1 Determine repository count in the CLI flow.
- [x] 1.2 Gate per-repository and aggregate Plotly show() calls based on
  repository count and --no-plot-show.
- [x] 1.3 Add
eport.html auto-open for multi-repository runs when
  --no-plot-show is false.
- [x] 1.4 Ensure --no-plot-show suppresses all auto-open paths.

## 2. Validation

- [x] 2.1 Run single-repository analysis with and without --no-plot-show and
  confirm charts open only when allowed.
- [x] 2.2 Run multi-repository analysis with and without --no-plot-show and
  confirm only
eport.html opens when allowed.
