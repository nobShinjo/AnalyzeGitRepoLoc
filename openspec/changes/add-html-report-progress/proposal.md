# Change: Add HTML report progress indicator

## Why

HTML report generation can take significant time, so users need visible progress
to avoid confusion and confirm the CLI is still working.

## What Changes

- Add a console progress indicator for HTML report generation.
- Surface HTML report generation as a discrete progress step alongside other pipeline phases.

## Impact

- Affected specs: cli-interface
- Affected code: HTML report generation flow and CLI progress reporting
