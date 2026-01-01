## 1. Implementation

- [x] 1.1 Normalize optional CLI filters to treat omitted or empty values as unset
- [x] 1.2 Parse `--since`/`--until` only when provided and validate `since <= until`
- [x] 1.3 Ensure open-ended date filters are passed through to analysis without errors
- [x] 1.4 Update error handling to surface invalid date range input clearly
- [x] 1.5 Manual validation: run CLI with no filters and confirm it completes
- [x] 1.6 Manual validation: run CLI with only `--since` and only `--until`
- [x] 1.7 Manual validation: run CLI with `--since` after `--until` and confirm error
- [x] 1.8 Manual validation: run CLI with empty `--lang`, `--author-name`, `--exclude-dirs`
