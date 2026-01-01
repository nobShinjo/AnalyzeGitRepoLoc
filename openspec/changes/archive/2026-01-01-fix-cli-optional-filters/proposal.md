# Change: Fix handling of optional CLI filters

## Why

The CLI currently raises errors when optional filters like `--since` or `--until` are omitted or provided as empty values. The tool should handle missing filters gracefully and validate date ranges consistently.

## What Changes

- Treat omitted or empty filter options (`--since`, `--until`, `--lang`, `--author-name`, `--exclude-dirs`) as unset.
- Support open-ended date filtering when only `--since` or only `--until` is provided.
- Validate date ranges and report an error when `--since` is after `--until`.

## Impact

- Affected specs: cli-interface, analysis-pipeline
- Affected code: CLI argument handling and filter normalization (`analyze_git_repo_loc/__main__.py`, `analyze_git_repo_loc/utils.py`)
- User-visible behavior: running without optional filters no longer crashes; invalid date ranges fail fast with a clear error.
