# Change: Update HTML report progress bar display

## MODIFIED Requirements

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
