## ADDED Requirements
### Requirement: Parallel repository analysis
The system SHALL analyze multiple repositories concurrently when the worker
count is greater than 1, and SHALL process each repository independently.

#### Scenario: Multiple repositories with workers
- **WHEN** the user provides multiple repositories and workers > 1
- **THEN** the system analyzes repositories in parallel and produces the same per-repo outputs as sequential analysis.

### Requirement: Deterministic repository ordering
The system SHALL produce aggregated outputs in a deterministic repository order
that follows the input repository list.

#### Scenario: Deterministic ordering
- **WHEN** repositories are analyzed in parallel
- **THEN** aggregated outputs preserve the input repository order.
