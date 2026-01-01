# Change: Refactor utils for remote auth and remote repo isolation

## Why

`utils.py` has accumulated remote repository and authentication concerns, making
maintenance and comprehension harder. We want to apply the single responsibility
principle and keep behavior unchanged while improving code organization.

## What Changes

- Extract remote repository clone/update helpers into dedicated module(s).
- Extract remote authentication helpers into dedicated module(s).
- Keep CLI parsing and generic helpers in `utils.py` or appropriately scoped
  modules.
- Preserve existing behavior, outputs, and error handling.

## Impact

- Affected specs: remote-auth, remote-repos
- Affected code: `analyze_git_repo_loc/utils.py`, new modules under
  `analyze_git_repo_loc/`
