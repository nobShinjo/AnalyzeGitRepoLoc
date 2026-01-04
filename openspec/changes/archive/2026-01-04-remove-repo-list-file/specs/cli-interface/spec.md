## MODIFIED Requirements

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
