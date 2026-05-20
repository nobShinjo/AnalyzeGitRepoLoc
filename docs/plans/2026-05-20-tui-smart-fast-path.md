# TUI Smart Fast Path Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `--tui` feel lighter by skipping obvious provider/auth prompts, showing a compact review first, and printing generated output paths at the end.

**Architecture:** Keep the existing thin-wrapper architecture. Add small helpers to `tui_wizard.py` and `tui_auth.py`, keep `run_tui_wizard(args, config_data)` as the handoff point, and add a display-only summary in `__main__.py` after report generation.

**Tech Stack:** Python 3.14+, prompt_toolkit, colorama, pytest, uv.

---

### Task 1: Add Auth Auto-Selection Helper

**Files:**
- Modify: `analyze_git_repo_loc/tui_auth.py`
- Test: `tests/test_tui_repo_selector.py`

**Step 1: Write the failing tests**

Add tests that build auth statuses with env token, CLI token, device code, and
one-time token availability. Verify the helper picks the first available
non-interactive method and returns `None` when only one-time token is available.

```python
def test_choose_auto_auth_prefers_cli_when_env_missing():
    statuses = [
        AuthMethodStatus("env_token", "env", False, "missing"),
        AuthMethodStatus("cli", "gh", True, "logged in", token="cli-token"),
        AuthMethodStatus("device_code", "device", True, "available"),
        AuthMethodStatus("one_time_token", "paste", True, "available"),
    ]

    assert choose_auto_auth_status(statuses).method == "cli"


def test_choose_auto_auth_skips_one_time_token():
    statuses = [
        AuthMethodStatus("one_time_token", "paste", True, "available"),
    ]

    assert choose_auto_auth_status(statuses) is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: FAIL because `choose_auto_auth_status` does not exist.

**Step 3: Implement the helper**

Add:

```python
def choose_auto_auth_status(
    statuses: list[AuthMethodStatus],
) -> AuthMethodStatus | None:
    """Return a safe non-interactive authentication status when available."""
    for status in statuses:
        if status.method == "one_time_token":
            continue
        if status.available:
            return status
    return None
```

**Step 4: Run tests**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: PASS for the new auth helper tests.

**Step 5: Commit**

```bash
git add analyze_git_repo_loc/tui_auth.py tests/test_tui_repo_selector.py
git commit -m "feat(tui): add auth auto selection helper"
```

### Task 2: Add Provider Fast Path

**Files:**
- Modify: `analyze_git_repo_loc/tui_wizard.py`
- Test: `tests/test_tui_repo_selector.py`

**Step 1: Write the failing tests**

Add tests for a helper that returns the only enabled provider target when config
is unambiguous, and returns `None` when multiple providers are enabled.

```python
def test_choose_auto_provider_target_returns_single_enabled_provider():
    settings = TuiSettings(
        providers={"github": ProviderSettings(enabled=True)},
        defaults=TuiDefaults(),
        quick_defaults=TuiQuickDefaults(),
    )

    target = choose_auto_provider_targets(settings)

    assert target is not None
    assert [item.key for item in target] == ["github"]


def test_choose_auto_provider_target_returns_none_for_multiple_enabled_providers():
    settings = TuiSettings(
        providers={
            "github": ProviderSettings(enabled=True),
            "gitlab": ProviderSettings(enabled=True),
        },
        defaults=TuiDefaults(),
        quick_defaults=TuiQuickDefaults(),
    )

    assert choose_auto_provider_targets(settings) is None
```

Adjust names to match existing settings dataclasses in `remote_catalog.py`.

**Step 2: Run tests to verify they fail**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: FAIL because the helper does not exist.

**Step 3: Implement the helper**

Add `choose_auto_provider_targets(settings)` near provider selection helpers.
Return the enabled provider list only when its length is one. Otherwise return
`None`.

**Step 4: Use the helper in `run_tui_wizard`**

Replace direct provider prompting with:

```python
provider_targets = choose_auto_provider_targets(settings)
if provider_targets is None:
    provider_targets = _prompt_provider_selection(settings)
```

**Step 5: Run tests**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add analyze_git_repo_loc/tui_wizard.py tests/test_tui_repo_selector.py
git commit -m "feat(tui): skip obvious provider prompt"
```

### Task 3: Wire Auth Fast Path Into the Wizard

**Files:**
- Modify: `analyze_git_repo_loc/tui_auth.py`
- Modify: `analyze_git_repo_loc/tui_wizard.py`
- Test: `tests/test_tui_repo_selector.py`

**Step 1: Write the failing tests**

Add a test that injects available CLI auth and verifies the wizard auth resolver
does not prompt when auto mode is allowed. Use monkeypatching around prompt calls
or the existing injection seams.

**Step 2: Run tests to verify failure**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: FAIL because wizard auth still always prompts.

**Step 3: Implement auto auth flow**

Add an optional parameter to the auth selector, for example:

```python
def run_tui_auth_selector(settings: Any, *, auto: bool = False) -> dict[str, str]:
```

When `auto=True`, call `choose_auto_auth_status(statuses)`. If it returns a
status, resolve it without prompting. If not, fall back to `_prompt_choice`.

**Step 4: Keep display labels**

Record a non-secret auth label for review, such as `gh`, `env`, or
`device code`. Store it in wizard state if needed; do not save it to config.

**Step 5: Run tests**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add analyze_git_repo_loc/tui_auth.py analyze_git_repo_loc/tui_wizard.py tests/test_tui_repo_selector.py
git commit -m "feat(tui): auto select obvious authentication"
```

### Task 4: Split Quick Review Into Compact and Detailed Modes

**Files:**
- Modify: `analyze_git_repo_loc/tui_wizard.py`
- Test: `tests/test_tui_repo_selector.py`

**Step 1: Write failing render tests**

Add tests for:

- compact review includes the one-line summary
- compact review does not include every repository line
- detailed review includes repository details
- recommended languages remain visible in compact form

**Step 2: Run tests to verify failure**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: FAIL because only one review mode exists.

**Step 3: Implement render modes**

Change `render_final_review` to accept:

```python
def render_final_review(
    state: TuiWizardState,
    *,
    color: bool = False,
    detailed: bool = False,
) -> str:
```

Compact mode prints:

- title
- one-line summary
- output
- suggestions
- action hint

Detailed mode prints the current full body.

**Step 4: Run tests**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add analyze_git_repo_loc/tui_wizard.py tests/test_tui_repo_selector.py
git commit -m "feat(tui): add compact quick review"
```

### Task 5: Add Short Action Keys and Details Toggle

**Files:**
- Modify: `analyze_git_repo_loc/tui_wizard.py`
- Test: `tests/test_tui_repo_selector.py`

**Step 1: Write failing action tests**

Add tests for parsing:

- blank input -> `run`
- `e` and `edit` -> `edit`
- `d` and `details` -> details display
- `s` and `save` -> `save`
- `c` and `cancel` -> `cancel`

**Step 2: Run tests to verify failure**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: FAIL because short keys are not supported.

**Step 3: Implement action normalization**

Add:

```python
def normalize_final_action(raw: str) -> str | None:
    value = raw.strip().casefold()
    if value == "":
        return "run"
    aliases = {
        "r": "run",
        "run": "run",
        "e": "edit",
        "edit": "edit",
        "d": "details",
        "details": "details",
        "s": "save",
        "save": "save",
        "c": "cancel",
        "cancel": "cancel",
    }
    return aliases.get(value)
```

**Step 4: Update `_prompt_final_action`**

Render compact mode by default. If action is `details`, render detailed mode
once, then ask again.

**Step 5: Run tests**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add analyze_git_repo_loc/tui_wizard.py tests/test_tui_repo_selector.py
git commit -m "feat(tui): add quick review action shortcuts"
```

### Task 6: Add End-of-Run Artifact Summary

**Files:**
- Modify: `analyze_git_repo_loc/__main__.py`
- Test: `tests/test_tui_repo_selector.py` or a new focused CLI helper test file

**Step 1: Write failing summary test**

Extract a helper that formats output summary lines and test it:

```python
def test_format_output_summary_lists_artifacts():
    lines = format_output_summary(Path("out/20260520123456"))

    assert "Report:" in lines
    assert "Summary:" in lines
    assert "Data:" in lines
```

Use exact filenames from the existing report and summary generation code.

**Step 2: Run tests to verify failure**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: FAIL because the helper does not exist.

**Step 3: Implement formatter**

Add a small public or private helper in `__main__.py`:

```python
def _format_output_summary(output_dir: Path) -> list[str]:
    return [
        "Finished",
        f"Report: {output_dir / 'index.html'}",
        f"Summary: {output_dir / 'summary.md'}",
        f"Data: {output_dir / '*.csv'}",
    ]
```

Adjust filenames to match the actual generated artifact names.

**Step 4: Print after report generation**

Use `ColoredConsolePrinter` and existing colorama styles. Keep `FINISH` for
compatibility if desired, but make the artifact paths visible before or after it.

**Step 5: Run tests**

Run: `uv run --group dev -m pytest tests/test_tui_repo_selector.py -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add analyze_git_repo_loc/__main__.py tests/test_tui_repo_selector.py
git commit -m "feat(cli): show output artifact summary"
```

### Task 7: Update Docs and Full Verification

**Files:**
- Modify: `README.md`
- Test: full suite

**Step 1: Update README**

Document the shorter TUI action keys and fast-path behavior:

```markdown
When only one provider is configured and a non-interactive authentication method
is available, `--tui` starts at Quick Review. Press Enter to run, `e` to edit,
`d` for details, `s` to save config then run, or `c` to cancel.
```

**Step 2: Run full test suite**

Run: `uv run --group dev -m pytest`

Expected: all tests pass.

**Step 3: Run manual smoke command**

Run: `uv run python -m analyze_git_repo_loc --tui --config .\config.yml`

Expected:

- Provider selection is skipped when config has only GitHub enabled.
- GitHub authentication is skipped when `gh` or env token is available.
- Compact Quick Review appears first.
- `d` displays detailed review.
- Enter runs analysis.
- Final output summary lists generated artifacts.

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs(tui): document smart quick review"
```
