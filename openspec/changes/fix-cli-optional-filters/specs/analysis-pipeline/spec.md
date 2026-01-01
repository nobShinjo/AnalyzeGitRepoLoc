## MODIFIED Requirements

### Requirement: Filtering

The system SHALL support filtering by date range (`--since`, `--until`), language
(`--lang`), author (`--author-name`), and excluded directories.
The system SHALL support open-ended date ranges when only `--since` or only
`--until` is provided.
The system SHALL validate that `--since` is not later than `--until` when both
are provided and SHALL report a fatal error when the range is invalid.

#### Scenario: Date range filter

- **WHEN** the user specifies `--since` and `--until`
- **THEN** only commits within that range are analyzed.

#### Scenario: Open-ended since

- **WHEN** the user specifies `--since` without `--until`
- **THEN** only commits on or after the start date are analyzed.

#### Scenario: Open-ended until

- **WHEN** the user specifies `--until` without `--since`
- **THEN** only commits on or before the end date are analyzed.

#### Scenario: Invalid date range

- **WHEN** the user specifies `--since` later than `--until`
- **THEN** the system reports a fatal error and exits.
