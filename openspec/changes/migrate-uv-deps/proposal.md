# Change: Migrate dependency management to uv

## Why

The project should standardize on uv for faster, reproducible dependency management and retire the pip-tools workflow.

## What Changes

- Replace requirements.in/requirements.txt and dev-requirements.* with pyproject.toml and uv.lock.
- Make uv the primary workflow for installing dependencies.
- Add pip-licenses as a required dependency for generating 3rd-party licenses.
- Update documentation to reflect the uv-first workflow.

## Impact

- Affected specs: dependency-management
- Affected code: dependency metadata (pyproject.toml/uv.lock), documentation (README.md, AGENTS.md, docs/requirements.md)
- **BREAKING**: requirements*.txt and pip-tools workflows are removed.
