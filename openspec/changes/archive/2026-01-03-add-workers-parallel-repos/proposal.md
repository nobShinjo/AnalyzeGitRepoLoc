# Change: Add worker settings and parallel repository analysis

## Why
Repository analysis can be slow for multiple repositories on multi-core machines.
Allowing users to control worker count and enabling repository-level parallelism
should improve performance without changing results.

## What Changes
- Add `--workers` CLI option and YAML `settings.workers` to control concurrency.
- Analyze repositories in parallel when workers > 1.
- Keep deterministic output ordering and progress reporting.

## Impact
- Affected specs: cli-interface, yaml-config, analysis-pipeline, runtime-constraints
- Affected code: analyze_git_repo_loc/utils.py, analyze_git_repo_loc/yaml_config.py
