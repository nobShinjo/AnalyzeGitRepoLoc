## 1. Implementation

- [x] 1.1 Update the progress event model to include commit totals and advances.
- [x] 1.2 Emit commit-based progress updates from repository analysis.
- [x] 1.3 Render child progress bars based on commit totals, including zero.
- [x] 1.4 Keep existing progress bars readable while updating parallel status.

## 2. Verification

- [x] 2.1 Run with multiple repositories and workers > 1 and confirm child bars
      advance with commit counts.
- [x] 2.2 Confirm progress bars remain aligned with no broken lines.
- [x] 2.3 Verify sequential runs (workers=1) keep current output unchanged.
