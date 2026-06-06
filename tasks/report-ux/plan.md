# Report UX Implementation Plan

## Steps

1. Add failing tests that describe lazy rendering, dashboard structure, and
   bounded filter panels.
2. Update templates with dashboard-oriented sections and data markers for
   tables, charts, and render state.
3. Replace eager all-tab rendering with active-tab rendering and first-open
   repository tab rendering.
4. Keep filter state initialized for every tab, but draw tag pills only for the
   tab being viewed.
5. Verify with focused tests, full pytest, and Browser smoke checks.

## Commit Shape

- `docs(report): plan report UX refresh`
- `feat(report): improve report rendering UX`
