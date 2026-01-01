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

- Create a local environment in `.venv`.
- Use `python -m venv .venv`.
- Activate:
  - Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
  - macOS/Linux: `source .venv/bin/activate`
- Deactivate with `deactivate`.

## uv

- Use `uv` for fast installs when available.
- Example:
  - `uv pip install -r requirements.txt`
  - `uv pip install -r dev-requirements.txt`

## pip-tools

- Source files: `requirements.in`, `dev-requirements.in`.
- Compile with `pip-compile` to update lock files:
  - `pip-compile requirements.in`
  - `pip-compile dev-requirements.in`
- Install with:
  - `pip install -r requirements.txt`
  - `pip install -r dev-requirements.txt`

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

## Docstrings

- Add docstrings to all public modules, classes, and functions.
- Use a consistent style (Google or NumPy) and keep it concise.
