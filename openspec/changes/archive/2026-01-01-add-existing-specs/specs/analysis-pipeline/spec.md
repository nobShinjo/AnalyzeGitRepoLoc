# Capability: analysis-pipeline

## ADDED Requirements

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

#### Scenario: Date range filter

- **WHEN** the user specifies `--since` and `--until`
- **THEN** only commits within that range are analyzed.

#### Scenario: Language and author filters

- **WHEN** the user specifies `--lang` or `--author-name`
- **THEN** only matching languages or authors are included.

#### Scenario: Excluded directories

- **WHEN** excluded directories are specified
- **THEN** files under those directories are not analyzed.

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
