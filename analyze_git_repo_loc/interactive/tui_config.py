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


def _build_provider_config(state: TuiWizardState) -> dict[str, Any]:
    providers: dict[str, Any] = {
        "github": {"enabled": False, "api_base_url": "https://api.github.com"},
        "gitlab": {"enabled": False, "base_url": "https://gitlab.com"},
    }
    for target in state.provider_targets:
        if target.provider == "github":
            providers["github"] = {
                "enabled": True,
                "api_base_url": target.base_url,
            }
        elif target.provider == "gitlab":
            providers["gitlab"] = {
                "enabled": True,
                "base_url": target.base_url,
            }
    return providers


def _build_repository_entry(
    state: TuiWizardState,
    repository: SelectedRepositoryConfig,
) -> dict[str, Any]:
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
    return entry


def _apply_shared_state_settings(
    target: dict[str, Any],
    state: TuiWizardState,
) -> None:
    if state.exclude_template_names:
        target["exclude_template_names"] = state.exclude_template_names
    if state.exclude_template_files:
        target["exclude_template_files"] = state.exclude_template_files
    if state.since is not None:
        target["since"] = _format_date(state.since)
    if state.until is not None:
        target["until"] = _format_date(state.until)
    if state.author_name:
        target["author_name"] = state.author_name
    if state.lang:
        target["lang"] = state.lang
    if state.global_exclude_dirs:
        target["exclude_dirs"] = state.global_exclude_dirs
    if state.workers is not None:
        target["workers"] = state.workers


def _build_settings(state: TuiWizardState) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "output": str(state.output),
        "interval": state.interval,
        "clear_cache": state.clear_cache,
        "no_plot_show": state.no_plot_show,
        "exclude_template_mode": state.exclude_template_mode,
    }
    _apply_shared_state_settings(settings, state)
    return settings


def _build_quick_defaults(state: TuiWizardState) -> dict[str, Any]:
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
    _apply_shared_state_settings(quick_defaults, state)
    return quick_defaults


def _render_yaml_text(data: dict[str, Any]) -> str:
    rendered = yaml.safe_dump(data, sort_keys=False)
    if isinstance(rendered, bytes):
        return rendered.decode("utf-8")
    if rendered is None:
        raise TypeError("yaml.safe_dump returned no YAML text.")
    return rendered


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
    providers = _build_provider_config(state)
    repositories = [
        _build_repository_entry(state, repository)
        for repository in state.selected_repositories
    ]
    return {
        "settings": _build_settings(state),
        "repositories": repositories,
        "interactive": {
            "providers": providers,
            "defaults": {"clone_protocol": state.clone_protocol},
            "quick_defaults": _build_quick_defaults(state),
        },
    }


def save_wizard_config(path: Path, state: TuiWizardState) -> None:
    """Save non-secret wizard settings to YAML."""
    path.write_text(
        _render_yaml_text(wizard_state_to_config(state)),
        encoding="utf-8",
    )
