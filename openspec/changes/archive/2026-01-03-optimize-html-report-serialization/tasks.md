## 1. Implementation
- [x] 1.1 Replace per-row Python loops in filter row serialization with a vectorized pandas transformation.
- [x] 1.2 Preserve progress callback behavior for filter row generation.
- [x] 1.3 Keep filter row schema and ordering stable.

## 2. Verification
- [x] 2.1 Compare report output for the same input before and after the change.
- [x] 2.2 Confirm progress bars update and complete for large datasets.
