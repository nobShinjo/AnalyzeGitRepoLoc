## 1. Implementation

- [ ] 1.1 Create pyproject.toml with minimal project metadata and runtime dependencies
- [ ] 1.2 Add pip-licenses to required dependencies
- [ ] 1.3 Generate uv.lock with uv for Python 3.14+ resolution
- [ ] 1.4 Remove requirements.in/requirements.txt and dev-requirements.*
- [ ] 1.5 Update README.md, AGENTS.md, and docs/requirements.md to uv-only guidance
- [ ] 1.6 Manual validation: run `uv sync` and `python -m analyze_git_repo_loc --help`
- [ ] 1.7 Manual validation: generate 3rd-party licenses using pip-licenses
