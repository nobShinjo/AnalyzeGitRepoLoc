# yaml-config Specification

## Purpose
TBD - created by archiving change add-yaml-config. Update Purpose after archive.
## Requirements
### Requirement: YAML configuration file

The system SHALL load analysis settings from a YAML configuration file when provided.

#### Scenario: YAML config provided

- **WHEN** the user supplies a YAML configuration file
- **THEN** the system loads settings from that file for the analysis run

### Requirement: CLI overrides YAML

The system SHALL apply CLI arguments with higher precedence than YAML configuration values.

#### Scenario: CLI override

- **WHEN** a setting is defined in both YAML and CLI
- **THEN** the CLI value is used for the analysis run

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

