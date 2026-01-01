## 1. Implementation

- [x] 1.1 Inventory `utils.py` remote/auth helpers and define target module boundaries.
- [x] 1.2 Create dedicated modules (e.g., `remote_auth.py`, `remote_repos.py`) with
      moved functions and docstrings.
- [x] 1.3 Update imports and call sites to use the new modules without changing
      public behavior.
- [x] 1.4 Confirm error/log output remains consistent after refactor.
- [x] 1.5 Manual validation (.venv): local repo, HTTPS (token), HTTPS (no token),
      and SSH flows.
