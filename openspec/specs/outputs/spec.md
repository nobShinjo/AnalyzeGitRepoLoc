# outputs Specification

## Purpose
Specify output directories, generated artifacts, charts, and cache behavior.
## Requirements
### Requirement: Output directory structure

The system SHALL write outputs under the configured output path, creating
per-repository subdirectories and a timestamped run directory named
`YYYYMMDDHHMMSS`.

#### Scenario: Timestamped run directory

- **WHEN** a run completes
- **THEN** a timestamped directory is created under the output path.

### Requirement: Per-repository artifacts

The system SHALL write the following artifacts under each
`<output>/<repository>/` directory:

- `loc_data.csv`
- `language_trends.csv`
- `author_trends.csv`
- `language_trend_data.csv`
- `language_summary_data.csv`
- `language_chart.html`
- `author_trend_data.csv`
- `author_summary_data.csv`
- `author_chart.html`

#### Scenario: Per-repository output

- **WHEN** a repository is analyzed
- **THEN** its output directory contains the listed CSV and HTML files.

### Requirement: Run-level artifacts

The system SHALL write the following artifacts under each
`<output>/<timestamp>/` directory:

- `language_analysis.csv`
- `author_analysis.csv`
- `repository_trend_analysis.csv`
- `repo_list.txt`
- `repository_trend_data.csv`
- `repository_summary_data.csv`
- `repository_chart.html`
- `author_trend_data.csv`
- `author_summary_data.csv`
- `author_chart.html`
- `author_contribution_summary_data.csv`
- `author_contribution_contribution_chart.html`

#### Scenario: Run-level output

- **WHEN** analysis completes
- **THEN** the run directory contains the listed CSV and HTML files.

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

### Requirement: Cache artifacts

The system SHALL cache commit analysis under
`<output>/.cache/<repository>/commit_data.pkl` and SHALL clear cached data before
analysis when `--clear-cache` is set.

#### Scenario: Clear cache

- **WHEN** the user passes `--clear-cache`
- **THEN** existing cache files are removed before analysis starts.

