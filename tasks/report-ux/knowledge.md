# Report UX Knowledge

## Current Architecture

- `html_report.py` builds one template context with `overview`, `repo_tabs`, and
  `filter_data_json`.
- `report.html.j2` embeds `window.reportFilterData` and renders tables/charts in
  browser JavaScript.
- `overview.html.j2` and `repo_tab.html.j2` provide tab panes and placeholders.

## Useful Constraints

- Keep generated reports offline-friendly.
- Plotly resize should be scheduled after a hidden tab becomes visible.
- Tag filter state can be initialized early because it is cheap compared with
  drawing charts and tables.
- Avoid changing analysis result semantics in a UI-only wave.

## Test Strategy

- Template tests should assert behavior-oriented markers, not entire HTML.
- Generated report smoke tests should include multiple repositories and long
  names.
- Browser verification should cover initial Overview, tab switching, tag search,
  and narrow viewport layout.
