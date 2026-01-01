# Capability: cli-interface

## ADDED Requirements
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

#### Scenario: Interval selection
- **WHEN** the user specifies `--interval weekly`
- **THEN** the system groups analysis by week.

#### Scenario: Output path default
- **WHEN** the user omits `--output`
- **THEN** the system writes outputs under `./out`.

### Requirement: Console progress and fatal error reporting
The system SHALL display progress to the console and SHALL terminate with an error
message on fatal errors.

#### Scenario: Fatal error
- **WHEN** an unrecoverable error occurs
- **THEN** the system prints an error message and exits.
