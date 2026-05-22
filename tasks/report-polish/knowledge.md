# Report Polish Knowledge

## Current Findings

- `getTickConfig()` returns `dtick: "D1"` for date reports, which can crowd
  daily ranges.
- `Repository list` is currently built as a comma-separated string in
  `HtmlReportBuilder._build_overview_context()`.
- Remote cache paths intentionally use `repo-name-<sha1-prefix>`, but analyzer
  display data can read the cached directory name instead of the original
  repository reference.
- Tab activation currently calls chart rendering as part of the same render path.
- Header height is dominated by navbar defaults, hero padding, and H1 sizing.

## Implementation Notes

- Display names and DOM ids should remain separate concepts.
- Use tests that assert behavior-oriented markers rather than exact full HTML.
- Keep `config.yml` and `.serena/memories/` out of commits.
