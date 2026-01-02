# Project Development Guidelines

These instructions supplement the OpenSpec block above. If a request triggers
OpenSpec usage, follow those steps first, then apply the guidelines below.

<!-- OPENSPEC:START -->
## OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:

- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:

- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

## Python Project Basics

- Target runtime: Python 3.14+.
- Use `python -m analyze_git_repo_loc` to run the CLI.
- Keep dependencies minimal and explicit.
- Prefer clear, testable functions with small scopes.

## Markdownlint

- Ensure `AGENTS.md` follows Markdownlint rules: <https://github.com/DavidAnson/markdownlint/tree/v0.40.0>.

## Virtual Environments (venv)

- Use `.venv` for running commands and tests in this project.
- Create a local environment in `.venv`.
- Use `python -m venv .venv`.
- Activate:
  - Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
  - macOS/Linux: `source .venv/bin/activate`
- Deactivate with `deactivate`.

## uv

- Use `uv` for dependency management.
- Example:
  - `uv venv --python 3.14`
  - `.venv\\Scripts\\Activate.ps1` (PowerShell) or `source .venv/bin/activate`
  - `uv sync --active`
  - `uv lock`

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
