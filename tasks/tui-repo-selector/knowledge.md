# GitHub/GitLab Repository Selector TUI Knowledge

## Existing Integration Points

- `analyze_git_repo_loc.utils.parse_arguments` owns CLI parsing, YAML merging,
  defaults, and validation.
- `analyze_git_repo_loc.__main__.main` runs parsing, then directly calls
  `analyze_git_repositories(args)`.
- `analyze_git_repo_loc.remote_repos.RemoteRepoManager` already accepts remote
  Git URLs and prepares local cached clones.
- `args.repo_paths` entries are `(Path | str, branch_name, exclude_dirs)`.

## Constraints

- Secrets stay in environment variables.
- API calls use `urllib.request` to avoid new HTTP dependencies.
- `prompt_toolkit` is imported only in the interactive TUI path.
- OpenSpec is intentionally not used for this change.

