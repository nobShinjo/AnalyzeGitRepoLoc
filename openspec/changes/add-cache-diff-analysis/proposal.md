# Change: Add cache reuse and diff analysis

## Why
Reusing cached commit analysis reduces runtime on repeated executions.

## What Changes
- Reuse cached commit analysis results where possible.
- Analyze only new or changed commits since the last run for the same repo and settings.

## Impact
- Affected specs: cache-diff-analysis
- Affected code: cache storage format, cache invalidation, commit analysis pipeline
