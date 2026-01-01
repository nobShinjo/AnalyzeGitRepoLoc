## Context

The repo currently uses requirements.in/requirements.txt and dev-requirements.* with pip-tools, but the plan is to move to uv and keep dependencies reproducible with uv.lock.

## Goals / Non-Goals

- Goals:
  - Use uv as the single dependency manager for the project.
  - Declare runtime dependencies in pyproject.toml and lock them in uv.lock.
  - Include pip-licenses as a required dependency to generate 3rd-party license files.
  - Update docs to match the new workflow.
- Non-Goals:
  - Changing application behavior or CLI features.
  - Introducing new runtime dependencies unrelated to current functionality.

## Decisions

- Use PEP 621 metadata in pyproject.toml with a minimal project definition.
- Keep the dependency list to direct runtime requirements plus pip-licenses.
- Remove requirements.in/requirements.txt and dev-requirements.* once uv is in place.

## Risks / Trade-offs

- Removing requirements files breaks existing workflows; mitigate by updating docs and providing uv commands.
- pip-licenses as a required dependency slightly increases install footprint; accepted for consistent license generation.

## Migration Plan

1. Create pyproject.toml and migrate direct dependencies from requirements.in.
2. Add pip-licenses to project dependencies.
3. Generate uv.lock with uv.
4. Remove requirements*.in/txt and pip-tools references.
5. Update documentation and verify uv workflow.

## Open Questions

- None.
