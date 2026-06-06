# Init Config Spec

## Purpose

Add a first-run configuration generator so users can create a minimal TUI-ready
YAML file without learning the full config schema first.

## Scope

- Add `--init` to the CLI.
- Treat `--init` as a setup mode that exits before analysis.
- Prompt for practical defaults:
  - config file path
  - GitHub provider enabled
  - GitLab provider enabled
  - output directory
  - interval
  - optional since/until dates
  - plot auto-display
  - cache policy
  - common exclude directories
- Write a minimal YAML config.
- Do not write `repositories`.
- Do not write secrets, tokens, client IDs, or auth choices.
- Print the next `--tui --config` command after creation.
- Expand the final analysis artifact summary.

## Behavior

- Default config path is `config.yml`.
- If the chosen path exists, ask for another path.
- If the user enters the same existing path again, ask for overwrite
  confirmation.
- A declined overwrite returns to path selection.
- Parent directories for the chosen config path may be created.
- Empty optional dates are omitted from generated YAML.

## Acceptance Criteria

- `python -m analyze_git_repo_loc --init` can generate a TUI-ready config.
- Existing config files are not overwritten without explicit confirmation.
- Generated config can be used with
  `python -m analyze_git_repo_loc --tui --config <path>`.
- Existing normal CLI and `--tui --config` parsing still works.
