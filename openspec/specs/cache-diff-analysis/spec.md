# cache-diff-analysis Specification

## Purpose
TBD - created by archiving change add-cache-diff-analysis. Update Purpose after archive.
## Requirements
### Requirement: Incremental analysis from cache

The system SHALL reuse cached commit analysis and process only new commits for repeated runs.

#### Scenario: Cached commits present

- **WHEN** cached analysis exists for a repository
- **THEN** the system processes only commits not already in cache

### Requirement: Cache invalidation on clear

The system SHALL recompute all analysis data when `--clear-cache` is used.

#### Scenario: Clear cache requested

- **WHEN** the user runs with `--clear-cache`
- **THEN** the system ignores cached data and recomputes analysis

