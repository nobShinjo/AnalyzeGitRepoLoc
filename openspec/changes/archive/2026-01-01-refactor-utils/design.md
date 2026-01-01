## Context

`analyze_git_repo_loc/utils.py` currently mixes CLI parsing, date normalization,
remote repository clone/update logic, and remote authentication helpers. Recent
remote-repos and remote-auth work increased complexity and made the module harder
to maintain.

## Goals / Non-Goals

- Goals:
  - Separate remote auth and remote repo responsibilities into dedicated modules.
  - Keep public behavior, outputs, and error handling unchanged.
  - Improve readability and maintainability with minimal code movement.
- Non-Goals:
  - Change authentication behavior or selection order.
  - Introduce new dependencies or new CLI options.
  - Alter outputs, data formats, or cache behavior.

## Decisions

- Create dedicated modules for remote authentication and remote repository
  handling, leaving `utils.py` focused on CLI parsing and generic helpers.
- Preserve function signatures where possible to minimize call-site churn.
- Keep shared low-level helpers in a neutral location to avoid import cycles.
- Maintain the current logging strategy (including `tqdm.write`) for auth output.

## Risks / Trade-offs

- Risk: import cycles or missed helpers during extraction.
  - Mitigation: map dependencies before moving functions and keep shared
    utilities in a small common module if needed.
- Risk: subtle behavior changes from refactor.
  - Mitigation: move functions with minimal edits and perform manual validation.

## Migration Plan

1. Move remote auth helpers to a dedicated module.
2. Move remote repo clone/update helpers to a dedicated module.
3. Update imports and run manual validations.
4. Roll back by reverting to the pre-refactor `utils.py` if issues arise.

## Open Questions

- Final module names (`remote_auth.py`, `remote_repos.py`, or alternatives)?
- Should `utils.py` remain as a facade for legacy imports or be trimmed to
  strictly generic utilities?
