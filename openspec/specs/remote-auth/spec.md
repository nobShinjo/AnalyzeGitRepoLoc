# remote-auth Specification

## Purpose
TBD - created by archiving change add-remote-auth. Update Purpose after archive.
## Requirements
### Requirement: SSH-first authentication
The system SHALL attempt SSH key authentication first when the repository URL
uses SSH (for example, `git@...` or `ssh://...`).

#### Scenario: SSH key available
- **WHEN** the repository URL uses SSH
- **THEN** the system uses the configured SSH key to authenticate

### Requirement: Token-based HTTPS fallback
The system SHALL support GitHub/GitLab tokens via environment variables when
HTTPS authentication is required.

#### Scenario: HTTPS token provided
- **WHEN** the repository URL uses HTTPS and a token environment variable is set
- **THEN** the system uses the token for HTTPS authentication

### Requirement: Authentication module isolation

The system SHALL encapsulate remote authentication helpers in a dedicated module
separate from general-purpose utilities.

#### Scenario: Remote auth maintenance

- **WHEN** authentication logic is updated or debugged
- **THEN** changes are localized to the authentication module without modifying
  unrelated utilities

