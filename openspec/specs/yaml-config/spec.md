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

