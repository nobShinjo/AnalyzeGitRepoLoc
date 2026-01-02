# Change: Update HTML report progress bar display

## Why

The HTML report progress currently uses postfix text on a single tqdm bar, which makes
long-running phases feel stalled and does not match the desired parent/child progress
style. The CLI should show step progress on a parent bar, render child bars for
sub-steps, and avoid postfix output.

## What Changes

- Update HTML report progress reporting to use a parent tqdm bar with step descriptions.
- Render child tqdm bars for report sub-steps and clear them after completion.
- Remove postfix-based step labels from HTML report progress output.

## Impact

- Affected specs: cli-interface
- Affected code: analyze_git_repo_loc/__main__.py, analyze_git_repo_loc/html_report.py
