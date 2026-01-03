## Context

- Repository analysis runs in parallel and only a completion counter is shown.
- Users want to see evidence of concurrent work while keeping progress readable.

## Goals / Non-Goals

- Goals:
  - Show active repositories during parallel analysis.
  - Preserve existing progress bars and avoid log corruption.
- Non-Goals:
  - Change analysis results or output artifacts.
  - Introduce new runtime dependencies.

## Decisions

- Decision: Use a lightweight progress event channel from workers to the main
  process (start/total/advance/finish events).
- Decision: Render per-repository child progress bars (queued/running/done) to
  visualize parallel work and advance them using commit counts.
- Decision: Keep sequential runs unchanged to avoid noise for single-repo usage.

## Risks / Trade-offs

- Excessive status updates can slow output or clutter the console.
- Long repository names may require truncation to fit terminal width.

## Migration Plan

- No migration required. This is a display-only change.

## Open Questions

- None.
