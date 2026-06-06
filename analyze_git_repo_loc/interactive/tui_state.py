"""TUI wizard state models.

Description:
    Defines the interactive wizard state dataclasses and the quick-defaults
    loader used to seed a run before repository analysis starts.
Classes:
    ProviderTarget:
        Provider endpoint selected for repository discovery.
    SelectedRepositoryConfig:
        Per-repository runtime settings selected in the wizard.
    TuiWizardState:
        Complete pre-analysis interactive state before it is applied to CLI args.
Functions:
    load_quick_defaults:
        Load non-secret quick wizard defaults from config data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from analyze_git_repo_loc.remote.remote_catalog import RemoteRepositoryRef


@dataclass(frozen=True)
class ProviderTarget:
    """Provider endpoint selected for repository discovery."""

    key: str
    provider: str
    label: str
    base_url: str


@dataclass
class SelectedRepositoryConfig:
    """Per-repository runtime settings selected in the wizard."""

    ref: RemoteRepositoryRef
    branch: str
    cache_status: str = "missing"
    include_subpath: str | None = None
    exclude_dirs: list[str] = field(default_factory=list)
    exclude_template_mode: str | None = None
    exclude_template_names: list[str] | None = None

    def git_url(self, clone_protocol: str) -> str:
        """Return the repository URL for the selected clone protocol."""
        return self.ref.git_url(clone_protocol)


@dataclass
class TuiQuickDefaults:
    """Non-secret defaults used by the quick TUI review."""

    since: datetime | None = None
    until: datetime | None = None
    interval: str | None = None
    author_name: list[str] | None = None
    lang: list[str] | None = None
    exclude_dirs: list[str] | None = None
    exclude_template_mode: str | None = None
    exclude_template_names: list[str] | None = None
    exclude_template_files: list[str] | None = None
    workers: int | None = None
    output: Path | None = None
    cache_policy: str | None = None
    no_plot_show: bool | None = None


@dataclass
class LightweightRecommendations:
    """Recommendations inferred without cloning new repositories."""

    languages: list[str] = field(default_factory=list)
    exclude_dirs: list[str] = field(default_factory=list)
    detected_templates: list[str] = field(default_factory=list)
    language_source: str = "not detected"
    exclude_source: str = "exclude templates"


@dataclass
class TuiWizardState:
    """Complete TUI state before it is applied to parsed CLI args."""

    provider_targets: list[ProviderTarget]
    auth_tokens: dict[str, str]
    repository_catalog: list[RemoteRepositoryRef]
    selected_repositories: list[SelectedRepositoryConfig]
    auth_labels: dict[str, str] = field(default_factory=dict)
    clone_protocol: str = "https"
    since: datetime | None = None
    until: datetime | None = None
    interval: str = "monthly"
    author_name: list[str] | None = None
    lang: list[str] | None = None
    workers: int | None = None
    global_exclude_dirs: list[str] | None = None
    exclude_template_mode: str = "auto"
    exclude_template_names: list[str] | None = None
    exclude_template_files: list[str] | None = None
    output: Path = Path("./out")
    clear_cache: bool = False
    refresh_remote_cache_only: bool = False
    no_plot_show: bool = True
    recommendations: LightweightRecommendations = field(
        default_factory=LightweightRecommendations
    )


def load_quick_defaults(
    config_data: dict[str, Any],
    *,
    parse_date: Callable[[str], datetime | None],
    normalize_list_value: Callable[[Any], list[str] | None],
    parse_optional_bool: Callable[[Any, str], bool | None],
    parse_optional_int: Callable[[Any, str], int | None],
    normalize_exclude_template_mode: Callable[[Any], str],
) -> TuiQuickDefaults:
    """Load non-secret quick wizard defaults from config data."""
    interactive = config_data.get("interactive") or {}
    if not isinstance(interactive, dict):
        raise ValueError("YAML config 'interactive' must be a mapping.")
    quick_defaults = interactive.get("quick_defaults") or {}
    if not isinstance(quick_defaults, dict):
        raise ValueError("YAML config 'interactive.quick_defaults' must be a mapping.")

    interval = quick_defaults.get("interval")
    if interval is not None and interval not in {"daily", "weekly", "monthly"}:
        raise ValueError(
            "interactive.quick_defaults.interval must be daily, weekly, or monthly."
        )
    cache_policy = quick_defaults.get("cache_policy")
    if cache_policy is not None:
        cache_policy = str(cache_policy).strip().casefold()
        if cache_policy not in {"use", "update", "clear"}:
            raise ValueError(
                "interactive.quick_defaults.cache_policy must be use, update, or clear."
            )
    exclude_template_mode = quick_defaults.get("exclude_template_mode")
    if exclude_template_mode is not None:
        exclude_template_mode = normalize_exclude_template_mode(exclude_template_mode)

    return TuiQuickDefaults(
        since=parse_date(str(quick_defaults.get("since") or "")),
        until=parse_date(str(quick_defaults.get("until") or "")),
        interval=interval,
        author_name=normalize_list_value(quick_defaults.get("author_name")),
        lang=normalize_list_value(quick_defaults.get("lang")),
        exclude_dirs=normalize_list_value(quick_defaults.get("exclude_dirs")),
        exclude_template_mode=exclude_template_mode,
        exclude_template_names=normalize_list_value(
            quick_defaults.get("exclude_template_names")
        ),
        exclude_template_files=normalize_list_value(
            quick_defaults.get("exclude_template_files")
        ),
        workers=parse_optional_int(quick_defaults.get("workers"), "workers"),
        output=Path(quick_defaults["output"]) if quick_defaults.get("output") else None,
        cache_policy=cache_policy,
        no_plot_show=parse_optional_bool(
            quick_defaults.get("no_plot_show"),
            "no_plot_show",
        ),
    )
