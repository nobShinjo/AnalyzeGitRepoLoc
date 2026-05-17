# GitHub/GitLab Repository Selector TUI Plan

## Implementation Steps

1. Extend YAML loading so `--tui` config can omit `repositories`.
2. Add TUI config parsing helpers and default values.
3. Add remote repository catalog fetching for GitHub and GitLab.
4. Add a TUI selector state model that can be tested without terminal drawing.
5. Add a prompt_toolkit-backed selector that imports the dependency lazily.
6. Add CLI wiring that runs the selector and sets `args.repo_paths`.
7. Add docs and dependency metadata.
8. Add unit tests for config, argument validation, API normalization, selection
   conversion, and selector state transitions.

## Verification

- Run focused unit tests for the new modules.
- Run parser smoke checks for normal CLI and `--tui`.
- Run import/compile checks when the local Python environment is available.

