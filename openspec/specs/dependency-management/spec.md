# dependency-management Specification

## Purpose
TBD - created by archiving change migrate-uv-deps. Update Purpose after archive.
## Requirements
### Requirement: uv-managed dependencies

The project SHALL use uv as the dependency manager.

#### Scenario: Install dependencies with uv

- **WHEN** a developer sets up the project
- **THEN** dependencies are installed using uv commands

### Requirement: Dependency declaration and lockfile

The project SHALL declare runtime dependencies in pyproject.toml and provide a uv.lock for reproducible installs.

#### Scenario: Reproducible dependency install

- **WHEN** a developer runs the uv sync workflow
- **THEN** the environment is resolved using pyproject.toml and uv.lock

### Requirement: pip-licenses included

The project SHALL include pip-licenses as a required dependency for generating 3rd-party license files.

#### Scenario: License generation

- **WHEN** a developer generates 3rd-party licenses
- **THEN** pip-licenses is available without extra installs

### Requirement: Documentation updated for uv

Project documentation SHALL describe the uv-based dependency workflow and remove pip-tools instructions.

#### Scenario: Read setup instructions

- **WHEN** a developer reads the setup instructions
- **THEN** only uv-based steps are described

