# cli-interface Specification

## Purpose

Define the command-line interface, supported inputs, options, and error reporting.
## Requirements
### Requirement: CLI entrypoint

The system SHALL provide a CLI entrypoint invoked via `python -m analyze_git_repo_loc`.

#### Scenario: Show help

- **WHEN** the user runs `python -m analyze_git_repo_loc --help`
- **THEN** the CLI displays usage for `repo_paths` and the supported options.

### Requirement: Repository input formats

The system SHALL accept `repo_paths` as a comma-separated list of repository
paths or Git URLs and SHALL reject file-path inputs that point to a repository
list file.

#### Scenario: Comma-separated list

- **WHEN** the user passes `path1,path2`
- **THEN** the system parses both repositories for analysis.

#### Scenario: File input rejected

- **WHEN** the user passes an existing file path to `repo_paths`
- **THEN** the CLI reports an error that file-based repository lists are no
  longer supported and instructs the user to use a YAML config file instead.

### Requirement: Branch defaults and per-repo exclude directories

The system SHALL allow repository entries to specify a branch using
`repo_path#branch`, defaulting to `main` when omitted, and SHALL accept per-repository
exclude directories using `repo_path#branch,exclude1,exclude2`.

#### Scenario: Default branch

- **WHEN** a repository entry omits the branch name
- **THEN** the system uses `main`.

#### Scenario: Per-repo exclude directories

- **WHEN** a repository entry includes excluded directories after the first comma
- **THEN** those directories are excluded for that repository.

### Requirement: CLI options and defaults

The system SHALL support the options `--output`, `--since`, `--until`, `--interval`,
`--lang`, `--author-name`, `--exclude-dirs`, `--clear-cache`, and `--no-plot-show`.
The system SHALL accept dates in `YYYY-MM-DD` format, default `--interval` to
`monthly`, and default `--output` to `./out`.
The system SHALL treat omitted filter options or empty filter values as unset.

#### Scenario: Interval selection

- **WHEN** the user specifies `--interval weekly`
- **THEN** the system groups analysis by week.

#### Scenario: Output path default

- **WHEN** the user omits `--output`
- **THEN** the system writes outputs under `./out`.

#### Scenario: Optional filters omitted

- **WHEN** the user omits `--since`, `--until`, `--lang`, `--author-name`, and `--exclude-dirs`
- **THEN** the CLI proceeds without filter-related errors.

#### Scenario: Empty filter values

- **WHEN** the user passes an empty value for `--lang`, `--author-name`, or `--exclude-dirs`
- **THEN** the CLI treats those filters as unset.

### Requirement: Console progress and fatal error reporting

The system SHALL display progress to the console for major pipeline phases,
including HTML report generation, and SHALL terminate with an error message on
fatal errors. For chart generation, the system SHALL display a parent progress
bar that advances once per chart step, with five steps corresponding to the
language trend, author trend, repository trend, author contribution, and author
aggregate charts. The parent progress bar SHALL surface the active chart step in
its description while per-repository progress bars remain unchanged. When
analyzing multiple repositories with workers greater than 1, the system SHALL
render child progress bars per repository that surface active repositories and
completion state, and advance based on commit analysis progress without
corrupting existing progress bars.

#### Scenario: Fatal error

- **WHEN** an unrecoverable error occurs
- **THEN** the system prints an error message and exits.

#### Scenario: Chart generation progress

- **WHEN** the CLI starts generating charts
- **THEN** the console displays a five-step parent progress bar that updates its
  description to the active chart step while preserving per-repository progress
  bars.

#### Scenario: Parallel repository progress

- **WHEN** multiple repositories are analyzed with workers greater than 1
- **THEN** the console shows per-repository child progress bars that update as
  repositories start, advance through commit analysis, and finish.

### Requirement: Worker configuration option

The system SHALL support a `--workers` CLI option to control the maximum number
of repositories analyzed concurrently. When omitted, the system SHALL select a
default worker count based on available CPU cores (minimum 1) and SHALL NOT
exceed the number of repositories provided.

#### Scenario: Workers option provided

- **WHEN** the user runs the CLI with `--workers 4`
- **THEN** repository analysis uses up to 4 concurrent workers.

#### Scenario: Workers option omitted

- **WHEN** the user omits `--workers`
- **THEN** the system selects a default worker count based on CPU cores and repo count.

