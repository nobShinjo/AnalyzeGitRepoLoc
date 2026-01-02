# Change: Update chart generation progress reporting

## MODIFIED Requirements

### Requirement: Console progress and fatal error reporting

The system SHALL display progress to the console for major pipeline phases,
including HTML report generation, and SHALL terminate with an error message on
fatal errors. For chart generation, the system SHALL display a parent progress
bar that advances once per chart step, with five steps corresponding to the
language trend, author trend, repository trend, author contribution, and author
aggregate charts. The parent progress bar SHALL surface the active chart step in
its description while per-repository progress bars remain unchanged.

#### Scenario: Fatal error

- **WHEN** an unrecoverable error occurs
- **THEN** the system prints an error message and exits.

#### Scenario: Chart generation progress

- **WHEN** the CLI starts generating charts
- **THEN** the console displays a five-step parent progress bar that updates its
  description to the active chart step while preserving per-repository progress bars.
