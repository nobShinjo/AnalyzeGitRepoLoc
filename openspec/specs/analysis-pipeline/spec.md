# analysis-pipeline Specification

## Purpose
Describe how commit data is analyzed, filtered, and aggregated into outputs.
## Requirements
### Requirement: Commit history analysis

The system SHALL analyze non-merge commits for each repository and SHALL produce
commit-level records with `Datetime`, `Repository`, `Branch`, `Commit_hash`,
`Author`, `Language`, `NLOC_Added`, `NLOC_Deleted`, and `NLOC`.

#### Scenario: Merge commit excluded

- **WHEN** a commit is a merge commit
- **THEN** the system excludes it from analysis.

#### Scenario: Commit record fields

- **WHEN** a qualifying commit is analyzed
- **THEN** the record includes all required fields.

### Requirement: Language detection and LOC rules

The system SHALL determine language by file extension mapping and SHALL exclude
comment and blank lines from LOC counts. Files with unknown languages SHALL be
skipped.

#### Scenario: Unknown language

- **WHEN** a modified file has an unmapped extension
- **THEN** the file is excluded from LOC analysis.

#### Scenario: Comment and blank lines

- **WHEN** a modified file contains comment or blank lines
- **THEN** those lines are not counted in NLOC.

### Requirement: Filtering

The system SHALL support filtering by date range (`--since`, `--until`), language
(`--lang`), author (`--author-name`), and excluded directories.
The system SHALL support open-ended date ranges when only `--since` or only
`--until` is provided.
The system SHALL validate that `--since` is not later than `--until` when both
are provided and SHALL report a fatal error when the range is invalid.

#### Scenario: Date range filter

- **WHEN** the user specifies `--since` and `--until`
- **THEN** only commits within that range are analyzed.

#### Scenario: Open-ended since

- **WHEN** the user specifies `--since` without `--until`
- **THEN** only commits on or after the start date are analyzed.

#### Scenario: Open-ended until

- **WHEN** the user specifies `--until` without `--since`
- **THEN** only commits on or before the end date are analyzed.

#### Scenario: Invalid date range

- **WHEN** the user specifies `--since` later than `--until`
- **THEN** the system reports a fatal error and exits.

### Requirement: Trend aggregation

The system SHALL aggregate commit data by the selected interval (`daily`, `weekly`,
`monthly`) and category (`Language`, `Author`, `Repository`) to produce trend and
summary datasets.

#### Scenario: Monthly aggregation

- **WHEN** the user selects `--interval monthly`
- **THEN** aggregation is performed on monthly buckets.

### Requirement: Multi-repository analysis

The system SHALL accept multiple repositories in a single run and analyze each
repository independently.

#### Scenario: Multiple repositories

- **WHEN** the user provides multiple repository entries
- **THEN** the system analyzes each repository in the same run.

