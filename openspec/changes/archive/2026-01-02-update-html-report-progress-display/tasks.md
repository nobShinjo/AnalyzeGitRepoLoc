# Tasks: Update HTML report progress bar display

## 1. Implementation

- [x] 1.1 Review current HTML report progress callback flow and step breakdown.
- [x] 1.2 Update progress reporting to use a parent tqdm bar with step descriptions.
- [x] 1.3 Add child tqdm bars for report sub-steps with leave=False.
- [x] 1.4 Remove postfix-based progress labels from HTML report progress output.

## 2. Validation

- [x] 2.1 Run the CLI and confirm parent progress shows step names without postfix.
- [x] 2.2 Confirm child progress bars appear for sub-steps and clear on completion.
