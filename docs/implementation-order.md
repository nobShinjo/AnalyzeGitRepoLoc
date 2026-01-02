# Implementation Order

## Goal

Define the recommended implementation order for pending OpenSpec changes based on
requirements and proposal dependencies.

## Ordered Changes

- [x] 1. add-remote-repos
- [x] 2. add-remote-auth
- [x] 3. add-yaml-config
- [x] 4. add-yaml-multi-repo-config
- [x] 5. add-cache-diff-analysis
- [x] ~~6. add-period-diff~~
- [x] 7. add-markdown-summary
- [x] 8. add-html-report
- [x] 9. add-report-filters
- [ ] 10. update-plot-display-behavior
- [ ] 11. add-html-report-progress

## Dependency Notes

- add-remote-auth depends on add-remote-repos.
- add-yaml-multi-repo-config depends on add-yaml-config.
- add-report-filters depends on add-html-report.

## Open Questions

- Cache-diff: when search filters/options change, existing cache may be invalid.
- HTML: prefer adopting an existing template or OSS report UI if available.
