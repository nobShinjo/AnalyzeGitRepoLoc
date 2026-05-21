# Init Config First-Run Design

## Summary

Add an interactive `--init` mode that helps first-time users create a practical
minimal configuration file before running the existing TUI analysis flow.

The goal is to reduce the friction around writing `config.yml` by hand while
preserving the current boundaries: secrets remain runtime-only, repositories are
selected by the TUI, and normal CLI/TUI analysis continues to use the existing
pipeline.

## Goals

- Let users run `python -m analyze_git_repo_loc --init` to create a starter
  config.
- Use `config.yml` as the default output path.
- Avoid silent overwrites. If the target exists, ask for another path; if the
  same path is entered again, require explicit overwrite confirmation.
- Generate a minimal useful config for TUI usage without storing repositories
  or authentication secrets.
- Print the next command after config creation:
  `python -m analyze_git_repo_loc --tui --config <path>`.
- Expand the final analysis output summary so users can find generated
  artifacts after the first run.

## Non-Goals

- Do not replace the existing CLI or TUI wizard.
- Do not store tokens, client IDs, or authentication choices.
- Do not save selected repositories during `--init`.
- Do not change LOC analysis, chart generation, or report generation behavior.
- Do not add a new TUI framework for this first wave.

## User Flow

1. User runs `python -m analyze_git_repo_loc --init`.
2. The CLI prompts for provider enablement, common analysis defaults, output
   path, cache policy, plot display, and common exclude directories.
3. The CLI proposes `config.yml` as the config path.
4. If the path exists, the CLI asks for a file name/path again.
5. If the user deliberately enters an existing path, the CLI asks for overwrite
   confirmation.
6. The config file is written.
7. The CLI prints a short success message and the next TUI command.

## Generated Config Shape

The generated YAML should include only stable, non-secret defaults:

```yaml
settings:
  output: out
  interval: monthly
  clear_cache: false
  no_plot_show: true
  since: null
  until: null
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
  quick_defaults:
    interval: monthly
    cache_policy: use
    no_plot_show: true
    exclude_dirs:
      - node_modules
      - .venv
```

Omit `repositories` by default so repository selection remains a TUI concern.
Omit keys with empty optional values if that keeps the generated YAML clearer.

## Output Summary

After analysis, print a compact artifact summary with:

- `report.html`
- `summary.md`
- run CSV directory
- per-repository chart root
- cache root

This is display-only and should not change output generation.

## Testing

- Unit-test config data construction and YAML rendering.
- Unit-test output path resolution, existing-file handling, and overwrite
  confirmation behavior.
- Unit-test that generated config data does not include secrets or
  repositories.
- Unit-test final output summary formatting.
- Run the existing TUI and remote repository tests.
