# Implementation Order

## Goal

Define the recommended implementation order for pending OpenSpec changes based on
requirements and proposal dependencies.

## Ordered Changes

- [x] 1. add-remote-repos
- [x] 2. add-remote-auth
- [ ] 3. add-yaml-config
- [ ] 4. add-yaml-multi-repo-config
- [ ] 5. add-cache-diff-analysis
- [ ] 6. add-period-diff
- [ ] 7. add-markdown-summary
- [ ] 8. add-html-report
- [ ] 9. add-report-filters

## Dependency Notes

- add-remote-auth depends on add-remote-repos.
- add-yaml-multi-repo-config depends on add-yaml-config.
- add-report-filters depends on add-html-report.

## Open Questions

- YAML schema strictness: required fields and defaults need definition.
- Cache-diff: when search filters/options change, existing cache may be invalid.
- HTML: prefer adopting an existing template or OSS report UI if available.
