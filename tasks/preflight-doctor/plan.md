# Preflight Doctor Plan

## Implementation Steps

1. Add focused tests for diagnostic results and CLI parsing.
2. Implement a small diagnostic module with reusable result objects.
3. Wire `doctor` into the CLI before analysis starts.
4. Render lightweight diagnostics in the TUI final review.
5. Update README and CHANGELOG for v3.0.0 release notes.
6. Run focused tests, then the full test suite.

## Verification

- `uv run --group dev -m pytest tests/test_doctor.py`
- `uv run --group dev -m pytest tests/test_tui_repo_selector.py`
- `uv run --group dev -m pytest`
