## MODIFIED Requirements

### Requirement: CLI options and defaults

The system SHALL support the options `--output`, `--since`, `--until`, `--interval`,
`--lang`, `--author-name`, `--exclude-dirs`, `--clear-cache`, and `--no-plot-show`.
The system SHALL accept dates in `YYYY-MM-DD` format, default `--interval` to
`monthly`, and default `--output` to `./out`.
The system SHALL treat omitted filter options or empty filter values as unset.

#### Scenario: Interval selection

- **WHEN** the user specifies `--interval weekly`
- **THEN** the system groups analysis by week.

#### Scenario: Output path default

- **WHEN** the user omits `--output`
- **THEN** the system writes outputs under `./out`.

#### Scenario: Optional filters omitted

- **WHEN** the user omits `--since`, `--until`, `--lang`, `--author-name`, and `--exclude-dirs`
- **THEN** the CLI proceeds without filter-related errors.

#### Scenario: Empty filter values

- **WHEN** the user passes an empty value for `--lang`, `--author-name`, or `--exclude-dirs`
- **THEN** the CLI treats those filters as unset.
