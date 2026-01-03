## Context
- Multi-repository analysis is currently sequential in `analyze_git_repo_loc/utils.py`.
- Commit traversal already uses internal parallelism via pydriller.
- Progress reporting must remain readable while repositories run in parallel.

## Goals / Non-Goals
- Goals:
  - Add user-configurable worker count.
  - Parallelize repository analysis while keeping deterministic outputs.
  - Keep progress reporting consistent with existing CLI behavior.
- Non-Goals:
  - Change commit analysis logic or filtering behavior.
  - Introduce new runtime dependencies.

## Decisions
- Decision: Use process-based parallelism for repository analysis tasks.
- Decision: Default worker count is `min(cpu_count, repo_count)` with a minimum of 1.
- Decision: Preserve output ordering based on the input repository list.
- Decision: Only the main process updates progress bars.

## Risks / Trade-offs
- Over-parallelization vs internal pydriller workers.
- Progress bar noise if per-repo output is not aggregated.

## Migration Plan
- No migration required; `--workers` is optional.

## Open Questions
- Should the default worker count subtract 1 to reduce contention?
