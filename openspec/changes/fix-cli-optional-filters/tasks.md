## 1. Implementation

- [ ] 1.1 Normalize optional CLI filters to treat omitted or empty values as unset
- [ ] 1.2 Parse `--since`/`--until` only when provided and validate `since <= until`
- [ ] 1.3 Ensure open-ended date filters are passed through to analysis without errors
- [ ] 1.4 Update error handling to surface invalid date range input clearly
- [ ] 1.5 Manual validation: run CLI with no filters and confirm it completes
- [ ] 1.6 Manual validation: run CLI with only `--since` and only `--until`
- [ ] 1.7 Manual validation: run CLI with `--since` after `--until` and confirm error
- [ ] 1.8 Manual validation: run CLI with empty `--lang`, `--author-name`, `--exclude-dirs`
