## 1. Implementation
- [x] 1.1 Add `--workers` to CLI args and YAML settings with validation and defaults.
- [x] 1.2 Implement repository-level parallel analysis with a bounded worker count.
- [x] 1.3 Preserve deterministic ordering for aggregated outputs.
- [x] 1.4 Preserve repository analysis progress reporting in parallel execution.

## 2. Verification
- [x] 2.1 Compare outputs for workers=1 vs workers>1 on the same input.
- [x] 2.2 Confirm progress bars display correctly during parallel execution.
- [x] 2.3 Verify YAML `workers` and CLI `--workers` precedence.
