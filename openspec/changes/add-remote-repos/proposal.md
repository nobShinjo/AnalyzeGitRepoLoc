# Change: Add remote repository analysis

## Why

Supporting git URLs expands the tool to work without local clones.

## What Changes

- Accept git URLs in `repo_paths` input.
- Clone remote repositories into a reusable cache directory for analysis.

## Impact

- Affected specs: remote-repos
- Affected code: repo input parsing, clone/cache management, cleanup logic
