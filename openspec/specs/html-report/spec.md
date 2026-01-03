# html-report Specification

## Purpose
TBD - created by archiving change add-html-report. Update Purpose after archive.
## Requirements
### Requirement: Single HTML report with tabs

The system SHALL generate a single HTML report that includes an overview tab and per-repository detail tabs.

#### Scenario: Multiple repositories analyzed

- **WHEN** the user analyzes multiple repositories
- **THEN** the generated HTML report contains an overview tab and one detail tab per repository

### Requirement: Filter payload batching
The system SHALL serialize filter rows from aggregated detail analysis in
batches and SHALL report progress after each batch during HTML report generation.

#### Scenario: Large filter payload
- **WHEN** the report includes many filter rows
- **THEN** the progress callback reports batch updates while the payload is generated.

### Requirement: Stable filter row schema
The system SHALL emit filter rows with the fields `interval`, `repository`,
`author`, `language`, `nloc_added`, `nloc_deleted`, and `nloc`.

#### Scenario: Filter row schema
- **WHEN** filter rows are serialized
- **THEN** each row contains the required fields.

