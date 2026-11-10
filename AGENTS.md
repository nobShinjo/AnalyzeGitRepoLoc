# Project Development Guidelines

## Python Project Basics

- Target runtime: Python 3.14+.
- Use `uv run analyze-git-repo-loc` to run the CLI.
- Keep `uv run -m analyze_git_repo_loc` available as an alternate entry point.
- Keep dependencies minimal and explicit.
- Prefer clear, testable functions with small scopes.

## Markdownlint

- Ensure `AGENTS.md` follows Markdownlint rules: <https://github.com/DavidAnson/markdownlint/tree/v0.40.0>.

## Virtual Environments (venv)

- Use `.venv` for running commands and tests in this project.
- Run `uv venv --python 3.14`, then `uv sync --frozen`.
- uv selects the project `.venv`; manual activation is optional.

## uv

- Use `uv` for dependency management.
- On Windows, execute uv commands outside the sandbox using the escalation
  approval mechanism so uv can access its managed Python and cache.
- After dependency changes, run `uv lock`, `uv sync --frozen`, and
  `uv lock --check`.
- Run the full test suite with `uv run pytest`; the default `dev` group includes
  pytest and the project is installed into `.venv`.
- For CLI changes, check `--version` and help for the top level and each
  subcommand, then run `doctor` and a non-interactive analysis with a temporary
  configuration and repository.
- For release preparation, audit locked dependencies and regenerate
  `3rdPartyLicenses.md` with `uv run pip-licenses --format=markdown
  --ignore-packages analyze-git-repo-loc --output-file=3rdPartyLicenses.md`,
  then prepend a level-one Markdown heading.

## Project Documents and Local State

- Read [docs/requirements.md](docs/requirements.md) when changing public behavior.
  Update it to describe the current CLI and supported behavior.
- Put new work plans and verification evidence in [docs/plans/](docs/plans/).
- Treat [tasks/](tasks/) and dated older plans as historical records; unchecked
  boxes alone do not establish current work requirements.
- Preserve personal `config.yml` changes and exclude that file from release
  staging. Use temporary configurations for validation.
- Keep user-wide Codex settings outside the project change scope.

## Conventional Commits

Use Conventional Commits for all changes:

- Format: `type(scope): subject`
- Examples:
  - `feat(cli): add repository filter option`
  - `fix(parser): handle empty diff`
  - `docs(readme): update usage examples`
  - `chore(deps): bump pandas`

## Commit Language

All commit messages MUST be written in English.

## Response Language

- All assistant responses MUST be written in Japanese.

## Docstrings

- Add docstrings to all public modules, classes, and functions.
- Use a consistent style (Google or NumPy) and keep it concise.
- File header docstrings MUST include:
  - A one-line summary.
  - A Description section (up to ~5 lines).
  - Classes/Functions/Methods sections only when public items exist
    (omit the section entirely when none).
  - Classes/Functions/Methods list only public items and add a few-line summary
    with a tab indentation for each item.

## Module Responsibilities

- Keep modules focused on a single responsibility. When a file grows to include
  multiple concerns, split the code into dedicated modules and keep `utils.py`
  minimal.
