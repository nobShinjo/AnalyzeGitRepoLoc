# Capability: runtime-constraints

## ADDED Requirements

### Requirement: Supported Python version

The system SHALL run on Python 3.14 or newer.

#### Scenario: Supported runtime

- **WHEN** the user runs the CLI on Python 3.14+
- **THEN** the system is supported.

### Requirement: Declared dependencies

The system SHALL declare runtime dependencies in `requirements.txt`, including
`pandas`, `plotly`, `pydriller`, `gitpython`, `tqdm`, and `colorama`.

#### Scenario: Install dependencies

- **WHEN** the user installs from `requirements.txt`
- **THEN** the runtime dependencies are available.

### Requirement: Parallel commit analysis

The system SHALL use CPU-core-based parallelism during commit analysis for large
repositories.

#### Scenario: Parallel traversal

- **WHEN** a repository has many commits
- **THEN** analysis uses available CPU cores to traverse commits.

### Requirement: Deterministic results

The system SHALL produce deterministic results for the same repository state and
date range.

#### Scenario: Repeated runs

- **WHEN** the same repository state and date range are analyzed twice
- **THEN** the outputs are reproducible.

### Requirement: Output failure handling

The system SHALL terminate with an error if output directories or files cannot be
created.

#### Scenario: Output path failure

- **WHEN** the output directory cannot be created
- **THEN** the system exits with an error.
