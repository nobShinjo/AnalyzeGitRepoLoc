# Report Polish Follow-up Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve generated `report.html` readability and responsiveness for multi-repository and daily-interval analysis reports.

**Architecture:** Keep the single offline `report.html + assets` shape. Separate display names from cache paths, move long repository lists out of metric cards, and keep tab activation responsive by deferring expensive chart rendering.

**Tech Stack:** Python, Jinja2 templates, Plotly JavaScript, pytest, uv.

---

## Task 1: Report Planning Notes

**Files:**
- Create: `docs/plans/2026-05-22-report-polish-follow-up.md`
- Create: `tasks/report-polish/plan.md`
- Create: `tasks/report-polish/spec.md`
- Create: `tasks/report-polish/todo.md`
- Create: `tasks/report-polish/knowledge.md`

**Steps:**
1. Record the implementation goals and assumptions.
2. Commit the planning files before behavior changes.

## Task 2: Failing Tests

**Files:**
- Modify: `tests/test_html_report.py`
- Add or modify analyzer-level tests for repository display names.

**Steps:**
1. Add tests for repository list rendering as a list.
2. Add tests for adaptive daily x-axis config.
3. Add tests for chart queue markers.
4. Add tests that remote cache hash suffixes do not leak into `Repository` display values.
5. Run focused tests and confirm failures.

## Task 3: Repository Display Names

**Files:**
- Modify: `analyze_git_repo_loc/git_repo_loc_analyzer.py`
- Modify: `analyze_git_repo_loc/html_report.py`
- Modify: `analyze_git_repo_loc/templates/overview.html.j2`

**Steps:**
1. Use `repo_ref` for human-readable `Repository` labels.
2. Preserve hashed remote cache paths for clone identity.
3. Render repository lists as compact HTML lists outside the metric grid.

## Task 4: Chart and Layout Polish

**Files:**
- Modify: `analyze_git_repo_loc/templates/report.html.j2`

**Steps:**
1. Replace fixed daily `D1` ticks with data-count-aware x-axis config.
2. Queue chart rendering with animation-frame scheduling.
3. Show tab content immediately before charts finish.
4. Compress the navbar and hero area to roughly half the previous height.

## Task 5: Verification and Commits

**Steps:**
1. Run focused tests.
2. Run full pytest.
3. Generate or reuse a report and run browser-level smoke checks.
4. Commit in logical Conventional Commit groups.
