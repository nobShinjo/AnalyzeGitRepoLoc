## ADDED Requirements
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
