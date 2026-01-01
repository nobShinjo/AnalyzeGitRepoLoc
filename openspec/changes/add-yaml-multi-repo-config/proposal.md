# Change: Add multi-repo YAML config

## Why
Users want to define multiple repositories and per-repo settings in a single configuration file.

## What Changes
- Allow YAML to define multiple repositories.
- Support per-repository settings such as branch and excluded directories.

## Impact
- Affected specs: yaml-multi-repo-config
- Affected code: YAML schema, repo input parsing, per-repo option merging

## Dependencies
- Depends on change: add-yaml-config
