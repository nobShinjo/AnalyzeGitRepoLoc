# Preflight Doctor Spec

## Purpose

Add a diagnostic mode for v3.0.0 so users can validate configuration and
interactive defaults before running analysis.

## Requirements

- Add `doctor` as a top-level subcommand.
- Run lightweight local checks by default.
- Add `--remote` to check configured interactive providers against remote APIs.
- Add `--strict` so warnings cause a non-zero exit.
- Reuse lightweight diagnostics in the interactive final review.
- Do not clone repositories or run analysis from doctor mode.
- Do not store or print secrets.

## Diagnostics

- Validate YAML shape and existing config parsing rules.
- Check common settings: interval, date range, workers, output parent,
  exclude template files, and secret-like keys.
- Check repositories: path presence, local path existence, branch shape,
  `include_subpath` traversal, and per-repository exclude files.
- Check interactive settings when present.
- With `--remote`, verify required provider tokens are present and provider
  repository catalog fetching succeeds.

## Exit Codes

- `0`: no errors.
- `1`: errors, or warnings when `--strict` is enabled.
- argparse errors keep the standard parser behavior.
