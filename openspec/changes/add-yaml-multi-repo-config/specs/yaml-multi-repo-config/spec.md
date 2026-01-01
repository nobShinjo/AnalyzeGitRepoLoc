## ADDED Requirements
### Requirement: Multiple repositories in YAML
The YAML configuration SHALL support multiple repositories as inputs.

#### Scenario: Multiple repos defined
- **WHEN** the YAML file lists multiple repositories
- **THEN** the system analyzes each repository in the list

### Requirement: Per-repository settings
The YAML configuration SHALL support per-repository settings such as branch and excluded directories.

#### Scenario: Per-repo settings provided
- **WHEN** a repository entry includes branch or excluded directories
- **THEN** those settings are applied to that repository
