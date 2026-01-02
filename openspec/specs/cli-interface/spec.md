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

The system SHALL accept `repo_paths` as either a comma-separated list of repository
paths or Git URLs, or a text file with one repository entry per line.

#### Scenario: Comma-separated list

- **WHEN** the user passes `path1,path2`
- **THEN** the system parses both repositories for analysis.

#### Scenario: File input

- **WHEN** the user passes a file path
- **THEN** the system reads and parses one repository entry per line.

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
fatal errors. For HTML report generation, the system SHALL display a parent
progress bar that advances per report step and SHALL render child progress bars
for sub-steps. The parent progress bar SHALL surface the current step in its
description and SHALL NOT use postfix text. Child progress bars SHALL not remain
visible after completion.

#### Scenario: Fatal error

- **WHEN** an unrecoverable error occurs
- **THEN** the system prints an error message and exits.

#### Scenario: HTML report generation progress

- **WHEN** the CLI starts generating the HTML report
- **THEN** the console displays a parent progress bar with step descriptions and
  child progress bars for sub-steps, without postfix output.

#### Scenario: HTML report child progress cleanup

- **WHEN** a report sub-step completes
- **THEN** the child progress bar is cleared from the console.

