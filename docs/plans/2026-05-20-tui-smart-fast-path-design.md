# TUI Smart Fast Path Design

## Summary

Improve the `--tui` flow so common runs require fewer confirmations, while keeping
the full wizard available when the user wants to inspect or change settings.

The current wizard is functionally complete, but everyday usage still asks for
provider and authentication choices that often have an obvious default. The Quick
Review screen also repeats detail that is useful for inspection but visually heavy
for a normal run. This design keeps the existing pipeline and config boundaries,
and adds a lighter path over the same state model.

## Goals

- Let a normal configured GitHub or GitLab run start from Quick Review.
- Keep authentication secrets runtime-only and out of config files.
- Make Quick Review scannable by default, with details available on demand.
- Add a clear end-of-run output summary for generated report artifacts.
- Preserve the existing edit flow for repository, branch, path, output, cache,
  and display settings.

## Non-Goals

- Do not introduce a separate TUI framework.
- Do not save authentication method, token, or client ID.
- Do not change LOC analysis behavior, chart generation, or report generation.
- Do not automatically apply recommended language filters.

## User Flow

### Normal Run

When exactly one provider is enabled and a preferred authentication method is
available, the wizard skips provider and auth prompts.

```text
Quick Review
GitHub via gh | 2 repos | monthly | 2024-01-01 -> 2026-05-31 | cache: use | display: off
Output: out
Suggestions: Markdown, Python, YAML, JSON, Bourne Shell (+5 more)

[Enter] Run   e Edit   d Details   s Save+Run   c Cancel
```

Pressing Enter runs analysis. `d` opens the detailed review. `e` opens the edit
categories. `s` saves non-secret analysis settings, then runs analysis.

### Detailed Review

The detailed review contains the current full information:

- providers and resolved auth source labels
- repository count
- period, interval, filters, output, cache policy, display mode
- recommended languages and excludes
- per-repository branch, include subpath, cache status, and excludes

### Edit Flow

The existing edit categories remain, with one addition: provider and
authentication changes can restart the selection portion of the wizard when
needed. The fast path never removes the ability to explicitly choose a provider
or auth method.

### End-of-Run Summary

After report generation, the CLI prints a compact artifact summary:

```text
Finished
Report: out/20260520123456/index.html
Summary: out/20260520123456/summary.md
Data: out/20260520123456/*.csv
```

The summary should use existing console color support when available.

## Architecture

The implementation remains a thin wrapper over the existing analysis pipeline.
`run_tui_wizard(args, config_data)` still returns CLI-equivalent settings by
mutating the parsed `args` namespace. The new behavior is implemented as small
helpers around the existing `TuiWizardState`.

### Components

- `analyze_git_repo_loc/tui_wizard.py`
  - Add fast-path provider selection when configuration is unambiguous.
  - Add compact and detailed render modes for final review.
  - Add short action keys for run, edit, details, save+run, and cancel.

- `analyze_git_repo_loc/tui_auth.py`
  - Add an auth auto-selection helper that returns the preferred available
    method without prompting when it is safe.
  - Keep the manual selector for ambiguous or explicit edit cases.

- `analyze_git_repo_loc/__main__.py`
  - Add a small output artifact summary after report generation.

- `tests/test_tui_repo_selector.py`
  - Cover fast-path selection, compact review, details action, save+run action,
    and auth source labeling.

## Data Flow

1. Config and CLI values load as they do today.
2. TUI settings are converted into provider candidates.
3. Fast-path provider selection runs only when exactly one provider is enabled.
4. Auth auto-selection resolves a runtime token source only when a preferred
   available method exists.
5. Repository catalog fetch and quick defaults continue to populate
   `TuiWizardState`.
6. Compact Quick Review prompts for action.
7. Run or save+run applies wizard state to `args`.
8. Existing analysis pipeline runs unchanged.
9. Output summary prints paths derived from `output_dir`.

## Error Handling

- If provider selection is ambiguous, use the existing prompt.
- If no auth method can be auto-selected, use the existing auth prompt.
- If fast-path auth resolution fails, fall back to manual auth selection.
- If output summary paths cannot be determined, skip only the missing path line
  and still print `FINISH`.

## Testing

- Unit tests for fast-path provider selection.
- Unit tests for auth auto-selection ordering and fallback.
- Unit tests for compact and detailed review rendering.
- Unit tests for action parsing: Enter, `e`, `d`, `s`, `c`, and full words.
- Unit tests for output summary path rendering.
- Full test suite with `uv run --group dev -m pytest`.
