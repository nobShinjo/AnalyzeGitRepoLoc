"""Tests for canonical package import boundaries."""

from __future__ import annotations

from pathlib import Path


_FORBIDDEN_ROOT_MODULES = (
    "analysis_runner",
    "analysis_helpers",
    "git_repo_loc_analyzer",
    "exclude_templates",
    "yaml_config",
    "init_config",
    "init_wizard",
    "tui_wizard",
    "tui_state",
    "tui_config",
    "tui_review",
    "tui_auth",
    "tui_selector",
    "remote_auth",
    "remote_oauth",
    "remote_catalog",
    "remote_repos",
    "chart_builder",
    "chart_ticks",
    "html_report",
    "markdown_summary",
)


def test_source_and_tests_use_canonical_package_paths() -> None:
    """Source and tests should avoid deleted root-module import paths."""
    project_root = Path(__file__).resolve().parents[1]
    python_files = [
        *project_root.joinpath("analyze_git_repo_loc").rglob("*.py"),
        *project_root.joinpath("tests").rglob("*.py"),
    ]

    for file_path in python_files:
        text = file_path.read_text(encoding="utf-8")
        for module_name in _FORBIDDEN_ROOT_MODULES:
            needle = f"analyze_git_repo_loc.{module_name}"
            assert needle not in text, f"{file_path} still references legacy import {needle}"
