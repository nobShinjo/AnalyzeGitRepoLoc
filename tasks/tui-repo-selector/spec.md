# GitHub/GitLab Repository Selector TUI Spec

## Purpose

Add a thin TUI entry point that lets a user choose accessible GitHub and GitLab
repositories from a configured provider list, then run the existing analysis
pipeline without changing the normal CLI behavior.

## Scope

- Add `--tui` to the CLI.
- Require `--config` when `--tui` is used.
- Allow a TUI config file without `repositories`.
- Read non-secret provider settings from YAML.
- Read secrets only from `GITHUB_TOKEN` and `GITLAB_TOKEN`.
- Fetch accessible repositories from GitHub and GitLab APIs.
- Normalize provider responses into one internal repository reference model.
- Let the user search, move, toggle multiple repositories, select all visible
  entries, clear the selection, confirm, or cancel.
- Convert selected repositories into the existing `args.repo_paths` format and
  run the current analysis flow.

## Non-Goals

- No token input inside the TUI.
- No YAML generation-only mode.
- No new HTTP dependency.
- No OpenSpec change artifacts for this work.

## YAML Shape

```yaml
settings:
  output: ./out
  interval: monthly
  workers: 4
  clear_cache: false
  no_plot_show: true

tui:
  providers:
    github:
      enabled: true
      api_base_url: https://api.github.com
    gitlab:
      enabled: false
      base_url: https://gitlab.com
  defaults:
    clone_protocol: https
```

## Error Behavior

- Missing `--config` with `--tui` is an argument error.
- No enabled providers is a TUI setup error.
- Enabled provider without token is a TUI setup error.
- API failures surface as a user-facing TUI setup error.
- Empty API results surface as a user-facing TUI setup error.
- TUI cancel exits with code `1` before analysis starts.

