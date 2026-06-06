# Report UX Refresh Design

## Objective

Improve the generated HTML report so large multi-repository runs remain readable,
stable, and responsive without adding new runtime dependencies.

## Problems

- The report eagerly renders every table and chart during page load.
- Many repository tabs make the first render slow and visually noisy.
- Long repository, author, and language names can push cards and tables out of shape.
- Tag filters lack quick feedback about visible and total tag counts.
- The current visual hierarchy reads as raw generated output rather than an
  analysis dashboard.

## Decisions

- Keep the report as a single `report.html` plus local `assets`.
- Keep Python-side analysis and payload generation mostly unchanged.
- Render only the active tab at startup.
- Render repository tabs on first open and reuse them after that.
- Re-render only the current tab tables when tag filters change.
- Use a restrained dashboard style: compact metrics, clear tab navigation,
  bounded filter panels, stable chart heights, and readable tables.
- Do not add JavaScript or CSS package dependencies in this wave.

## Scope

- `analyze_git_repo_loc/templates/report.html.j2`
- `analyze_git_repo_loc/templates/overview.html.j2`
- `analyze_git_repo_loc/templates/repo_tab.html.j2`
- Focused report tests under `tests/`

## Out of Scope

- Splitting embedded data into separate JSON files.
- Changing chart generation semantics.
- Replacing Tabler or Plotly.
- Changing CLI or TUI behavior.

## Acceptance

- Initial page load renders Overview tables and charts only.
- Repository tabs render when selected and do not force all tabs to render.
- Tag search and filter interactions update only the current tab.
- Long names wrap without breaking the layout.
- Report UI has stable chart/table/card dimensions on desktop and narrow widths.
- Focused pytest coverage and Browser smoke verification pass.
