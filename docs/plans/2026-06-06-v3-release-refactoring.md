# v3.0.0 Release Refactoring Plan

## Goal

Prepare the v3.0.0 release with documentation consistency checks and a
low-risk refactoring backlog that improves maintainability without changing
released behavior.

## Release-Gating Cleanup

- Keep release edits limited to README, changelog, sample configuration,
  packaging metadata, and behavior-preserving code organization.
- Do not include local working state such as `config.yml`, IDE settings, or
  generated Serena/cache files in release commits unless explicitly requested.
- Rebuild the local Python environment before final verification because the
  current `.venv` points at a missing uv-managed Python executable.
- Regenerate CLI help snippets from the live command before publishing docs.

## Pre-v3.0.0 Refactoring Scope

- Treat `utils.py` as a compatibility surface and move only clearly delegated
  internals into focused modules when the move is behavior-neutral.
- Keep `interactive/tui_wizard.py` behavior unchanged for v3.0.0; only extract
  helpers if tests already cover the exact behavior being moved.
- Avoid large `init_wizard.py` controller/render/input rewrites before v3.0.0.
- Keep HTML report polish limited to naming, constants, and documentation
  alignment unless `tests/test_html_report.py` covers the change.

## Post-v3.0.0 Refactoring Backlog

- Split `interactive/tui_wizard.py` by provider selection, catalog loading,
  prompt flow, quick review rendering, and state persistence.
- Split `config/init_wizard.py` into controller state transitions, rendering,
  and prompt-toolkit runtime bindings.
- Move repository progress and analysis execution helpers out of `utils.py`
  while preserving historical imports for callers and tests.
- Extract HTML report context builders from `reporting/html_report.py` into
  focused overview, repository-tab, filter-row, and chart-resolution helpers.
- Add import-boundary tests for each extracted module before moving behavior.

## Verification Checklist

- Run focused tests first:
  `tests/test_doctor.py`, `tests/test_init_config.py`,
  `tests/test_tui_wizard.py`, `tests/test_tui_repo_selector.py`,
  `tests/test_html_report.py`.
- Run the full suite with `uv run --group dev -m pytest`.
- Run `python -m analyze_git_repo_loc --help`, `init --help`, `doctor --help`,
  and `run --help`; update README snippets if the output differs.
- Run Markdownlint against `README.md`, `README.ja.md`, `CHANGELOG.md`, and
  `AGENTS.md`.
- Confirm `git status --short` contains only intended release files before
  staging.
