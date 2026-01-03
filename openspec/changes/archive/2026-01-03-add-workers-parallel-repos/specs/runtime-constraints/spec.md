## ADDED Requirements
### Requirement: Repository-level parallelism bound
The system SHALL bound repository-level parallelism to the configured worker
count (minimum 1) to avoid over-subscription.

#### Scenario: Worker bound
- **WHEN** the worker count is set to 1
- **THEN** repository analysis runs sequentially.
