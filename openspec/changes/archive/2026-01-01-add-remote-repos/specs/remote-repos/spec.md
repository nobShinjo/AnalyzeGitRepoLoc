## ADDED Requirements

### Requirement: Git URL repositories

The system SHALL accept git URLs as repository inputs.

#### Scenario: Git URL provided

- **WHEN** a git URL is provided in `repo_paths`
- **THEN** the system clones the repository and analyzes it

### Requirement: Clone cache directory

The system SHALL store remote clones in a reusable cache directory.

#### Scenario: Reusing cached clone

- **WHEN** the same git URL is analyzed again
- **THEN** the system reuses the cached clone instead of recloning
