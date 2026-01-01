# Project Context

## Purpose

Analyze Git repositories and visualize LOC (net code lines) by language, author,
and repository. The CLI outputs CSV datasets and Plotly HTML charts for reporting.

## Tech Stack

- Python 3.14+
- CLI entrypoint: `python -m analyze_git_repo_loc`
- Core libraries: pydriller, gitpython, pandas, plotly, lizard, tqdm, colorama
- Outputs: CSV files and Plotly HTML charts

## Project Conventions

### Code Style

- Follow PEP 8 and use descriptive names.
- Keep functions small and testable.
- Add concise docstrings to public modules, classes, and functions.
- Keep dependencies minimal and explicit (requirements.in/requirements.txt).

### Architecture Patterns

- Single-package CLI with orchestration in `__main__.py`.
- Pipeline: parse git history (exclude merge commits) -> compute LOC by language/
  author -> aggregate by interval -> write CSV -> generate Plotly HTML charts.
- Cache commit data under `./out/.cache/<repo>/commit_data.pkl` for reuse.
- Multi-repository analysis runs in parallel (CPU core-based).

### Testing Strategy

- No automated test framework is documented yet.
- Manual verification: run CLI against a sample repo and confirm CSV/HTML outputs,
  filters, and cache behavior.

### Git Workflow

- Use Conventional Commits: `type(scope): subject` (English).
- When helpful, include the change intent in the commit body.
- GitHub flow: `main` as default, `feature/*` branches for changes.

## Domain Context

- Input supports local repository paths and git URLs, optionally `repo#branch`.
- `repo_paths` accepts comma-separated entries or a file (one repo per line).
- Language detection is extension-based (see `LANGUAGES.md`); unknown languages
  are skipped, and comment/blank lines are excluded from LOC.
- Filters: date range (`--since`, `--until`), interval (`daily|weekly|monthly`),
  languages, authors, excluded directories.
- Outputs include per-repo datasets and a timestamped run directory under `./out`.

## Important Constraints

- Python 3.14+ required.
- Deterministic results for the same repo state and date range.
- Fail with an error if output directories/files cannot be created.
- Large repositories should be handled via parallel commit analysis.
- No GUI or web API (CLI-only).

## External Dependencies

- Git repositories (local or remote via git URL).
- Python libraries listed in `requirements.txt` (pydriller, gitpython, pandas,
  plotly, lizard, tqdm, colorama, etc.).
