"""TUI final review rendering helpers.

Description:
    Renders the compact and detailed final review screens for the interactive
    wizard, including exclude recommendations and doctor diagnostics.
Functions:
    format_optional_list:
        Format an optional list for prompts and review text.
    format_compact_list:
        Format a list with a compact overflow marker.
    render_final_review:
        Render the final wizard review text.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from colorama import Fore, Style

from analyze_git_repo_loc.doctor import run_data_diagnostics
from analyze_git_repo_loc.exclude_templates import (
    build_exclude_recommendation,
    load_exclude_templates,
)
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.interactive.tui_config import wizard_state_to_config
from analyze_git_repo_loc.interactive.tui_state import (
    SelectedRepositoryConfig,
    TuiWizardState,
)


def format_optional_list(value: list[str] | None) -> str:
    """Format an optional list for prompts and review text."""
    return ", ".join(value) if value else "(none)"


def format_compact_list(value: list[str] | None, *, limit: int = 5) -> str:
    """Format a list with a compact overflow marker."""
    if not value:
        return "(none)"
    visible = value[:limit]
    suffix = ""
    remaining = len(value) - len(visible)
    if remaining > 0:
        suffix = f" (+{remaining} more)"
    return ", ".join(visible) + suffix


def _format_date(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.date().isoformat()


def _color(text: str, color: str, *, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{color}{text}{Style.RESET_ALL}"


def _cache_policy_label(state: TuiWizardState) -> str:
    cache_policy = "clear" if state.clear_cache else "use"
    if state.refresh_remote_cache_only:
        cache_policy = "update"
    return cache_policy


def _provider_review_label(state: TuiWizardState) -> str:
    values = []
    for target in state.provider_targets:
        label = target.label
        auth_label = state.auth_labels.get(target.key)
        if auth_label:
            label = f"{label} via {auth_label}"
        values.append(label)
    return ", ".join(values) or "(none)"


def _review_summary(state: TuiWizardState) -> str:
    repo_label = "repo" if len(state.selected_repositories) == 1 else "repos"
    return (
        f"{_provider_review_label(state)} | "
        f"{len(state.selected_repositories)} {repo_label} | {state.interval} | "
        f"{_format_date(state.since) or '(none)'} -> "
        f"{_format_date(state.until) or '(none)'} | "
        f"cache: {_cache_policy_label(state)} | "
        f"display: {'off' if state.no_plot_show else 'on'}"
    )


def _deduplicate_text(values: list[str]) -> list[str]:
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
    excludes = list(state.global_exclude_dirs or [])
    excludes.extend(repository.exclude_dirs)
    return _deduplicate_text(excludes) or None


def _combined_excludes(
    state: TuiWizardState,
    repository: SelectedRepositoryConfig,
    *,
    determine_cache_path: Callable[..., Path],
) -> list[str] | None:
    manual_excludes = _combined_manual_excludes(state, repository)
    cache_path = determine_cache_path(
        repository.ref,
        clone_protocol=state.clone_protocol,
        output=state.output,
    )
    if repository.include_subpath:
        cache_path = cache_path / repository.include_subpath
    recommendation = build_exclude_recommendation(
        cache_path,
        manual_excludes=manual_excludes,
        selected_template_names=(
            repository.exclude_template_names
            if repository.exclude_template_names is not None
            else state.exclude_template_names
        ),
        mode=repository.exclude_template_mode or state.exclude_template_mode,
        templates=load_exclude_templates(state.exclude_template_files),
    )
    return recommendation.paths or None


def render_final_review(
    state: TuiWizardState,
    *,
    determine_cache_path: Callable[..., Path],
    color: bool = False,
    detailed: bool = False,
) -> str:
    """Render the final wizard review."""
    providers = ", ".join(
        f"{target.label} ({target.base_url})" for target in state.provider_targets
    ) or tr("tui.none")
    cache_policy = _cache_policy_label(state)
    recommended_languages = (
        format_compact_list(state.recommendations.languages, limit=5)
        if state.recommendations.languages
        else tr("tui.none")
    )
    detected_templates = (
        format_compact_list(state.recommendations.detected_templates, limit=5)
        if state.recommendations.detected_templates
        else tr("tui.none")
    )
    doctor_result = run_data_diagnostics(wizard_state_to_config(state), remote=False)
    doctor_summary = (
        f"Doctor: {len(doctor_result.errors)} errors, "
        f"{len(doctor_result.warnings)} warnings"
    )
    summary = _review_summary(state)
    if not detailed:
        return "\n".join(
            [
                _color(tr("tui.quick_review"), Fore.CYAN + Style.BRIGHT, enabled=color),
                _color(summary, Fore.WHITE + Style.BRIGHT, enabled=color),
                tr("tui.output_line", path=state.output),
                tr(
                    "tui.suggestions",
                    value=recommended_languages,
                    source=state.recommendations.language_source,
                ),
                doctor_summary,
                "",
                _color(
                    tr("tui.final_actions"),
                    Fore.YELLOW,
                    enabled=color,
                ),
            ]
        )
    lines = [
        _color(tr("tui.quick_review"), Fore.CYAN + Style.BRIGHT, enabled=color),
        _color(summary, Fore.WHITE + Style.BRIGHT, enabled=color),
        tr("tui.providers", value=providers),
        tr("tui.repository_count", count=len(state.selected_repositories)),
        tr(
            "tui.period",
            since=_format_date(state.since) or tr("tui.none"),
            until=_format_date(state.until) or tr("tui.none"),
        ),
        tr("tui.interval", value=state.interval),
        tr("tui.authors", value=format_optional_list(state.author_name)),
        tr("tui.languages", value=format_compact_list(state.lang)),
        tr(
            "tui.recommended_languages",
            value=recommended_languages,
            source=state.recommendations.language_source,
        ),
        tr("tui.global_excludes", value=format_optional_list(state.global_exclude_dirs)),
        f"Exclude template mode: {state.exclude_template_mode}",
        f"Detected exclude templates: {detected_templates}",
        tr(
            "tui.recommended_excludes",
            value=format_compact_list(state.recommendations.exclude_dirs, limit=5),
        ),
        tr("tui.output_line", path=state.output),
        tr("tui.cache", policy=cache_policy),
        tr("tui.auto_display", value=tr("tui.off") if state.no_plot_show else tr("tui.on")),
        doctor_summary,
    ]
    for issue in doctor_result.issues:
        lines.append(f"[{issue.severity.upper()}] {issue.message}")
    lines.extend(
        [
            "",
            _color(tr("tui.repositories"), Fore.CYAN, enabled=color),
        ]
    )
    for repository in state.selected_repositories:
        include = repository.include_subpath or "."
        excludes = _combined_excludes(
            state,
            repository,
            determine_cache_path=determine_cache_path,
        )
        cache_status = _color(
            repository.cache_status,
            Fore.GREEN if repository.cache_status == "cached" else Fore.YELLOW,
            enabled=color,
        )
        lines.append(
            f"- {repository.ref.provider} {repository.ref.full_name} "
            f"branch={repository.branch} include={include} "
            f"cache={cache_status} excludes={format_compact_list(excludes)}"
        )
    return "\n".join(lines)
