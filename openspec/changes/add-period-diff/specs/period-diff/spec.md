## ADDED Requirements

### Requirement: Period comparison inputs

The system SHALL accept a baseline period for comparison with the target period.

#### Scenario: Baseline period provided

- **WHEN** the user supplies `--baseline-since` and `--baseline-until`
- **THEN** the system computes baseline aggregates alongside the target period

### Requirement: Diff outputs

The system SHALL output a diff table and chart comparing the target and baseline periods.

#### Scenario: Diff results generated

- **WHEN** both target and baseline periods are provided
- **THEN** the system writes diff outputs for the comparison
