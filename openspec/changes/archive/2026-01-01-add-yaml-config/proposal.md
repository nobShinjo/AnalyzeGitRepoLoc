# Change: Add YAML configuration file

## Why

Users need a reusable way to define analysis settings without repeating long CLI invocations.

## What Changes

- Add support for loading analysis settings from a YAML configuration file.
- Add a CLI option to point to the YAML file (proposed: `--config`).
- Define precedence so CLI arguments override YAML values.
- Define required fields and defaults for the YAML schema.

## Impact

- Affected specs: yaml-config
- Affected code: CLI option parsing, configuration loading/validation, run configuration assembly

## Decisions

- YAML uses a two-level structure with `settings` and `repositories`.
- `repositories` is required and contains a single entry for this change.
- Each repository entry MUST include `path`.
- Defaults: `interval=monthly`, `since/until` unset, `lang/author_name/exclude_dirs` unset.
- `output` is supported in `settings` and defaults to `./out` when omitted.
- Precedence: CLI > repository entry > settings.
