# Change: Add multi-repo YAML config

## Why

Users want to define multiple repositories and per-repo settings in a single configuration file.

## What Changes

- Allow YAML to define multiple repositories.
- Support per-repository settings such as branch and excluded directories.
- Define required fields and defaults for per-repository entries.

## Impact

- Affected specs: yaml-multi-repo-config
- Affected code: YAML schema, repo input parsing, per-repo option merging

## Decisions

- YAML uses the `settings` + `repositories` structure from `add-yaml-config`.
- `repositories` supports multiple entries.
- Each repository entry MUST include `path`.
- Defaults: `branch=main`, `exclude_dirs` unset, `lang/author_name` inherit from settings unless overridden.
- Precedence: CLI > repository entry > settings.

## Dependencies

- Depends on change: add-yaml-config
