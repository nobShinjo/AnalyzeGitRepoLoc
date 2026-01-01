# Change: Add specs for existing CLI capabilities

## Why

The current behavior is documented in README.md and docs/requirements.md, but
openspec/specs is empty. We need specs that describe what the system already
does.

## What Changes

- Document the CLI interface and repository input formats.
- Document analysis rules, filters, and aggregation behavior.
- Document output artifacts (CSV/HTML, cache, run directory).
- Document runtime constraints and non-functional requirements.
- No code changes.

## Impact

- Affected specs: cli-interface, analysis-pipeline, outputs, runtime-constraints
- Affected code: none (documentation only)
