# Report UX Spec

## Functional Requirements

- The report must render the Overview tab on first load.
- Repository tab charts and tables must not render until that tab is opened.
- Once a tab is rendered, switching away and back must preserve the rendered
  state and only resize charts.
- Tag search must update the visible tag list for the current tab.
- Tag filter changes must update current tab tables.
- The generated report must remain usable from `file://` without a server.

## UX Requirements

- Top-level metrics must be visible without scrolling on ordinary desktop
  windows.
- Tabs must support many repositories with horizontal scrolling.
- Filter cards must have bounded height and visible tag counts.
- Tables must wrap long text without changing page width.
- Chart panels must reserve stable vertical space before Plotly draws.

## Non-Functional Requirements

- No new package dependencies.
- Keep report generation deterministic enough for tests.
- Preserve existing data payload keys consumed by client-side filtering.
