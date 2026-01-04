# Change: Remove repo list file input from CLI

## Why

Simplify repository input handling and standardize multi-repository configuration
through YAML, reducing ambiguous CLI inputs.

## What Changes

- CLI no longer accepts `repo_paths` as a file containing repository entries.
- When a file path is supplied to `repo_paths`, the CLI reports an error and
  instructs using YAML config instead.
- Documentation and examples are updated to reflect the supported input format.

## Impact

- Affected specs: `cli-interface`
- Affected code: `analyze_git_repo_loc/utils.py`, `README.md`
