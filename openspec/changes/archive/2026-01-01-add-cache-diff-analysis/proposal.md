# Change: Add cache reuse and diff analysis

## Why

Reusing cached commit analysis reduces runtime on repeated executions.

## What Changes

- Reuse cached commit analysis results where possible.
- Analyze only new or changed commits since the last run for the same repo and settings.
- Invalidate or ignore cache when analysis filters or options change.

## Impact

- Affected specs: cache-diff-analysis
- Affected code: cache storage format, cache invalidation, commit analysis pipeline

## Decisions

- Cache key includes: repo (path/URL), branch, since, until, lang, author, exclude_dirs.
- Cache key normalization: sort lang/author/exclude_dirs, normalize paths, normalize dates to ISO.
- Cache is invalidated when any cache-key component changes.
- Cache diff uses the last analyzed commit hash as the resume point.
- Cache format includes a version tag; incompatible versions invalidate existing cache.
