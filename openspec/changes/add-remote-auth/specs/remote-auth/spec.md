## ADDED Requirements

### Requirement: SSH-first authentication

The system SHALL attempt SSH key authentication first for remote repository access.

#### Scenario: SSH key available

- **WHEN** the repository is accessed over SSH
- **THEN** the system uses the configured SSH key to authenticate

### Requirement: Token-based HTTPS fallback

The system SHALL support GitHub/GitLab tokens via environment variables when HTTPS authentication is required.

#### Scenario: HTTPS token provided

- **WHEN** SSH auth is unavailable and a token environment variable is set
- **THEN** the system uses the token for HTTPS authentication
