# Change: Update generate charts progress display

## Why

The chart generation progress bar currently reports four steps while executing
five chart tasks, and does not surface which step is in progress. Aligning the
step count and showing the active step in the parent bar makes progress clearer
without altering per-repository progress bars.

## What Changes

- Update the chart generation progress bar to report five steps.
- Display the current chart step in the parent progress bar description.
- Keep per-repository progress bars unchanged.

## Impact

- Affected specs: cli-interface
- Affected code: analyze_git_repo_loc/__main__.py
