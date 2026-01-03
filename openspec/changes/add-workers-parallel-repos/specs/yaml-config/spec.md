## ADDED Requirements
### Requirement: YAML workers setting
The system SHALL accept a `workers` setting under YAML `settings` to control
repository-level concurrency, and SHALL apply CLI `--workers` with higher
precedence.

#### Scenario: YAML workers provided
- **WHEN** the YAML settings include `workers: 2` and the CLI does not specify `--workers`
- **THEN** the analysis uses up to 2 workers.

#### Scenario: CLI overrides YAML workers
- **WHEN** YAML provides `workers: 2` and CLI provides `--workers 4`
- **THEN** the analysis uses up to 4 workers.
