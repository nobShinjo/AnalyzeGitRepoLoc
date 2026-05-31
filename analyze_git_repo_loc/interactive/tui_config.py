"""TUI wizard state application and export helpers.

Description:
    Converts interactive wizard state into runtime CLI arguments and non-secret
    YAML configuration structures. The module keeps state application logic
    separate from prompt orchestration.
Functions:
    apply_wizard_state:
        Apply confirmed wizard state to parsed CLI arguments.
    wizard_state_to_config:
        Convert wizard state into a YAML-safe non-secret config mapping.
    save_wizard_config:
        Save the exported wizard config to disk as YAML.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from analyze_git_repo_loc.interactive.tui_state import (
    SelectedRepositoryConfig,
    TuiWizardState,
)


def _format_date(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.date().isoformat()


def _deduplicate_text(values: list[str]) -> list[str]:
    """Return non-empty strings with stable de-duplication."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _combined_manual_excludes(
    state: TuiWizardState,
    repository: SelectedRepositoryConfig,
) -> list[str] | None:
    """Return manually configured global and per-repository excludes."""
    excludes = list(state.global_exclude_dirs or [])
    excludes.extend(repository.exclude_dirs)
    return _deduplicate_text(excludes) or None


def _filter_present_excludes(
    state: TuiWizardState,
    repository: SelectedRepositoryConfig,
    excludes: list[str] | None,
) -> list[str]:
    """Return selected excludes without dropping template paths that are absent now."""
    del state, repository
    return excludes or []


def apply_wizard_state(
    args: argparse.Namespace,
    state: TuiWizardState,
) -> argparse.Namespace:
    """Apply confirmed wizard state to parsed CLI arguments."""
    args.repo_paths = [
        (
            repository.git_url(state.clone_protocol),
            repository.branch or repository.ref.default_branch or "main",
            _filter_present_excludes(
                state,
                repository,
                _combined_manual_excludes(state, repository),
            ),
            repository.include_subpath,
            repository.exclude_template_mode,
            repository.exclude_template_names,
        )
        for repository in state.selected_repositories
    ]
    args.since = state.since
    args.until = state.until
    args.interval = state.interval
    args.author_name = state.author_name
    args.lang = state.lang
    args.exclude_dirs = None
    args.exclude_template_mode = state.exclude_template_mode
    args.exclude_template_names = state.exclude_template_names
    args.exclude_template_files = state.exclude_template_files
    args.workers = state.workers
    args.output = state.output
    args.clear_cache = state.clear_cache
    args.no_plot_show = state.no_plot_show
    return args


def wizard_state_to_config(state: TuiWizardState) -> dict[str, Any]:
    """Convert wizard state to a non-secret YAML configuration mapping."""
    providers: dict[str, Any] = {
        "github": {"enabled": False, "api_base_url": "https://api.github.com"},
        "gitlab": {"enabled": False, "base_url": "https://gitlab.com"},
    }
    for target in state.provider_targets:
        if target.provider == "github":
            providers["github"] = {"enabled": True, "api_base_url": target.base_url}
        if target.provider == "gitlab":
            providers["gitlab"] = {"enabled": True, "base_url": target.base_url}
    repositories = []
    for repository in state.selected_repositories:
        entry: dict[str, Any] = {
            "path": repository.git_url(state.clone_protocol),
            "branch": repository.branch or repository.ref.default_branch or "main",
        }
        if repository.exclude_dirs:
            entry["exclude_dirs"] = repository.exclude_dirs
        if repository.exclude_template_mode:
            entry["exclude_template_mode"] = repository.exclude_template_mode
        if repository.exclude_template_names:
            entry["exclude_template_names"] = repository.exclude_template_names
        if repository.include_subpath:
            entry["include_subpath"] = repository.include_subpath
        repositories.append(entry)
    settings: dict[str, Any] = {
        "output": str(state.output),
        "interval": state.interval,
        "clear_cache": state.clear_cache,
        "no_plot_show": state.no_plot_show,
        "exclude_template_mode": state.exclude_template_mode,
    }
    if state.exclude_template_names:
        settings["exclude_template_names"] = state.exclude_template_names
    if state.exclude_template_files:
        settings["exclude_template_files"] = state.exclude_template_files
    if state.since is not None:
        settings["since"] = _format_date(state.since)
    if state.until is not None:
        settings["until"] = _format_date(state.until)
    if state.author_name:
        settings["author_name"] = state.author_name
    if state.lang:
        settings["lang"] = state.lang
    if state.workers is not None:
        settings["workers"] = state.workers
    if state.global_exclude_dirs:
        settings["exclude_dirs"] = state.global_exclude_dirs
    cache_policy = "clear" if state.clear_cache else "use"
    if state.refresh_remote_cache_only:
        cache_policy = "update"
    quick_defaults: dict[str, Any] = {
        "output": str(state.output),
        "interval": state.interval,
        "cache_policy": cache_policy,
        "no_plot_show": state.no_plot_show,
        "exclude_template_mode": state.exclude_template_mode,
    }
    if state.exclude_template_names:
        quick_defaults["exclude_template_names"] = state.exclude_template_names
    if state.exclude_template_files:
        quick_defaults["exclude_template_files"] = state.exclude_template_files
    if state.since is not None:
        quick_defaults["since"] = _format_date(state.since)
    if state.until is not None:
        quick_defaults["until"] = _format_date(state.until)
    if state.author_name:
        quick_defaults["author_name"] = state.author_name
    if state.lang:
        quick_defaults["lang"] = state.lang
    if state.global_exclude_dirs:
        quick_defaults["exclude_dirs"] = state.global_exclude_dirs
    if state.workers is not None:
        quick_defaults["workers"] = state.workers
    return {
        "settings": settings,
        "repositories": repositories,
        "interactive": {
            "providers": providers,
            "defaults": {"clone_protocol": state.clone_protocol},
            "quick_defaults": quick_defaults,
        },
    }


def save_wizard_config(path: Path, state: TuiWizardState) -> None:
    """Save non-secret wizard settings to YAML."""
    path.write_text(
        yaml.safe_dump(wizard_state_to_config(state), sort_keys=False),
        encoding="utf-8",
    )
