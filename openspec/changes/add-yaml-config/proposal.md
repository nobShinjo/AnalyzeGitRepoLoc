# Change: Add YAML configuration file

## Why

Users need a reusable way to define analysis settings without repeating long CLI invocations.

## What Changes

- Add support for loading analysis settings from a YAML configuration file.
- Add a CLI option to point to the YAML file (proposed: `--config`).
- Define precedence so CLI arguments override YAML values.

## Impact

- Affected specs: yaml-config
- Affected code: CLI option parsing, configuration loading/validation, run configuration assembly
