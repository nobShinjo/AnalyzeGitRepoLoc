# Change: Add parallel repository progress visibility

## Why

Parallel repository analysis only updates the overall completion count, making it
hard to feel or verify that work is happening concurrently. A clearer progress
view will improve user confidence and observability during long runs.

## What Changes

- Display child progress bars for repositories during parallel analysis that
  advance based on commit counts.
- Surface running and completed repositories without corrupting existing
  progress bars.

## Impact

- Affected specs: cli-interface
- Affected code: analyze_git_repo_loc/utils.py, analyze_git_repo_loc/git_repo_loc_analyzer.py
