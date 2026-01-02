# Change: CLI progress for HTML report

## MODIFIED Requirements

### Requirement: Console progress and fatal error reporting

The system SHALL display progress to the console for major pipeline phases,
including HTML report generation, and SHALL terminate with an error message on
fatal errors.

#### Scenario: Fatal error

- **WHEN** an unrecoverable error occurs
- **THEN** the system prints an error message and exits.

#### Scenario: HTML report generation progress

- **WHEN** the CLI starts generating the HTML report
- **THEN** the console displays progress for the report generation phase.
