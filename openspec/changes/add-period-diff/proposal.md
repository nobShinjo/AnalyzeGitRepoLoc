# Change: Add period comparison outputs

## Why

Users need to compare two time ranges to see how contribution patterns change.

## What Changes

- Add baseline period inputs (proposed: `--baseline-since` and `--baseline-until`).
- Output a diff table and chart comparing target vs baseline periods.

## Impact

- Affected specs: period-diff
- Affected code: CLI parsing, aggregation logic, output generation
