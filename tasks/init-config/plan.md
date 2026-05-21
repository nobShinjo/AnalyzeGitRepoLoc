# Init Config Implementation Plan

## Task 1: Document the Design

- Add the design document under `docs/plans/`.
- Add `plan.md`, `spec.md`, `todo.md`, and `knowledge.md` under
  `tasks/init-config/`.
- Commit the documentation before production implementation.

## Task 2: Add Test Coverage First

- Add unit tests for init config data construction.
- Add unit tests for YAML rendering.
- Add unit tests for path selection and overwrite confirmation.
- Add unit tests for CLI `--init` dispatch.
- Add unit tests for expanded output summary formatting.

## Task 3: Implement Init Mode

- Add an init helper module with prompt injection seams for tests.
- Add `--init` argument parsing.
- Dispatch init mode before analysis starts.
- Keep generated config free of repositories and secrets.
- Print the next TUI command after writing the file.

## Task 4: Expand Output Summary

- Include report, markdown summary, run CSV directory, chart root, and cache root.
- Keep the change display-only.

## Task 5: Verify and Commit

- Run focused tests.
- Run the full pytest suite.
- Update README usage notes.
- Commit implementation with an English Conventional Commit message.
