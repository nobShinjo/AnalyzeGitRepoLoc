# Report Polish Spec

## Requirements

- Daily/date reports must not render one x-axis tick label per day for long ranges.
- Repository list must be rendered as an HTML list, not a comma-separated metric value.
- Remote cache hash suffixes must not appear in repository display names.
- Tab activation must update visible content before expensive chart rendering starts.
- Header plus hero height must be significantly smaller than the current report UX refresh.

## Constraints

- Keep the offline single-report architecture.
- Add no new package dependencies.
- Preserve hashed remote cache paths for clone collision avoidance.
- Do not touch local `config.yml` or `.serena/memories/`.
