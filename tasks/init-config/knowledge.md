# Init Config Knowledge

## Existing Boundaries

- `analyze_git_repo_loc.utils.parse_arguments` owns CLI arguments and config
  merging.
- `analyze_git_repo_loc.__main__.main` dispatches TUI selection before analysis.
- `--tui` currently requires `--config`.
- YAML settings are loaded before TUI execution and then applied to the existing
  analysis pipeline.
- TUI-selected repositories should flow into `args.repo_paths`; `--init` should
  not save repositories.

## Safety Rules

- Do not store `GITHUB_TOKEN`, `GITLAB_TOKEN`, host-specific token variables,
  OAuth client IDs, one-time tokens, or auth choices.
- Preserve CLI precedence for normal analysis.
- Preserve the thin TUI wrapper architecture.
- Do not resurrect file-based repository lists.

## Useful Verification

- Focused tests:
  `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`
- Full tests:
  `uv run --group dev -m pytest`
