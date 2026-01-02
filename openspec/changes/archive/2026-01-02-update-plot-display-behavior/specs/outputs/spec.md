# outputs spec delta

## MODIFIED Requirements

### Requirement: Plotly HTML charts

The system SHALL generate Plotly HTML charts for trend and summary views.
The system SHALL control interactive display based on repository count and
--no-plot-show.

#### Scenario: Suppress chart and report display

- **WHEN** the user passes --no-plot-show
- **THEN** the charts are generated but no charts or reports are opened
  interactively.

#### Scenario: Single repository interactive charts

- **WHEN** the user analyzes a single repository and does not pass
  --no-plot-show
- **THEN** the per-repository Language and Author charts are opened
  interactively.

#### Scenario: Multi-repository report auto-open

- **WHEN** the user analyzes multiple repositories and does not pass
  --no-plot-show
- **THEN** the system opens
eport.html in the run output directory and does
  not open any per-repository or aggregate Plotly charts interactively.
