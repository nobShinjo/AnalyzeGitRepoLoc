"""
Full pre-analysis flow for interactive repository runs.

Description:
    Builds and applies the runtime interactive state used before analysis. The flow
    reuses provider authentication and repository selection, then lets the user
    confirm branches, filters, output, cache, and display behavior.
Classes:
    ProviderTarget:
        Provider endpoint selected for repository discovery.
    SelectedRepositoryConfig:
        Per-repository runtime settings selected in the wizard.
    TuiWizardState:
        Complete pre-analysis interactive state before it is applied to CLI args.
Functions:
    run_tui_wizard:
        Run the interactive pre-analysis flow and update parsed CLI args.
    choose_auto_provider_targets:
        Choose the configured provider automatically when unambiguous.
    normalize_final_action:
        Normalize Quick Review action shortcuts.
    apply_wizard_state:
        Apply a wizard state to an argparse namespace.
    save_wizard_config:
        Save non-secret wizard settings to YAML.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from colorama import Fore, Style, just_fix_windows_console

from analyze_git_repo_loc.exclude_templates import (
    build_exclude_recommendation,
    load_exclude_templates,
    normalize_exclude_template_mode,
)
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.language_extensions import LanguageExtensions
from analyze_git_repo_loc.remote_catalog import (
    GitHubProviderSettings,
    GitLabProviderSettings,
    RemoteCatalogError,
    RemoteRepositoryRef,
    TuiDefaults,
    TuiProviderSettings,
    TuiSettings,
    fetch_github_branches,
    fetch_github_repositories,
    fetch_gitlab_branches,
    fetch_gitlab_repositories,
    load_tui_settings,
)
from analyze_git_repo_loc.remote_repos import RemoteRepoManager
from analyze_git_repo_loc.tui_auth import run_tui_auth_selection
from analyze_git_repo_loc.tui_selector import (
    RepositorySelectionResult,
    run_repository_selector,
)


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


def build_provider_targets(settings: TuiSettings) -> list[ProviderTarget]:
    """
    Build provider target descriptors from enabled TUI settings.

    Args:
        settings (TuiSettings): Loaded TUI settings.

    Returns:
        list[ProviderTarget]: Enabled provider endpoints.
    """
    targets: list[ProviderTarget] = []
    if settings.providers.github.enabled:
        targets.append(
            ProviderTarget(
                key="github",
                provider="github",
                label="GitHub",
                base_url=settings.providers.github.api_base_url,
            )
        )
    if settings.providers.gitlab.enabled:
        base_url = settings.providers.gitlab.base_url
        label = "GitLab.com" if base_url.rstrip("/") == "https://gitlab.com" else "GitLab"
        key = "gitlab.com" if label == "GitLab.com" else "gitlab.self_hosted"
        targets.append(
            ProviderTarget(
                key=key,
                provider="gitlab",
                label=label,
                base_url=base_url,
            )
        )
    return targets


def choose_auto_provider_targets(settings: TuiSettings) -> list[ProviderTarget] | None:
    """
    Return configured provider targets when the selection is unambiguous.

    Args:
        settings (TuiSettings): Loaded TUI settings.

    Returns:
        list[ProviderTarget] | None: The only enabled provider target, or None.
    """
    targets = build_provider_targets(settings)
    if len(targets) == 1:
        return targets
    return None


def build_provider_candidates(settings: TuiSettings) -> list[ProviderTarget]:
    """
    Build selectable provider candidates for the wizard.

    Args:
        settings (TuiSettings): Loaded TUI settings used as defaults.

    Returns:
        list[ProviderTarget]: GitHub, GitLab.com, and self-hosted GitLab candidates.
    """
    return [
        ProviderTarget(
            key="github",
            provider="github",
            label="GitHub",
            base_url=settings.providers.github.api_base_url,
        ),
        ProviderTarget(
            key="gitlab.com",
            provider="gitlab",
            label="GitLab.com",
            base_url="https://gitlab.com",
        ),
        ProviderTarget(
            key="gitlab.self_hosted",
            provider="gitlab",
            label="Self-hosted GitLab",
            base_url=settings.providers.gitlab.base_url
            if settings.providers.gitlab.base_url.rstrip("/") != "https://gitlab.com"
            else "",
        ),
    ]


def selected_targets_to_settings(
    targets: list[ProviderTarget],
    *,
    clone_protocol: str,
) -> TuiSettings:
    """
    Convert selected provider targets to single-provider TUI settings.

    Args:
        targets (list[ProviderTarget]): Selected targets.
        clone_protocol (str): Clone protocol default.

    Returns:
        TuiSettings: Settings for the first matching provider target.
    """
    github = next((target for target in targets if target.provider == "github"), None)
    gitlab = next((target for target in targets if target.provider == "gitlab"), None)
    return TuiSettings(
        providers=TuiProviderSettings(
            github=GitHubProviderSettings(
                enabled=github is not None,
                api_base_url=github.base_url if github else "https://api.github.com",
            ),
            gitlab=GitLabProviderSettings(
                enabled=gitlab is not None,
                base_url=gitlab.base_url if gitlab else "https://gitlab.com",
            ),
        ),
        defaults=TuiDefaults(clone_protocol=clone_protocol),
    )


def target_to_settings(target: ProviderTarget, *, clone_protocol: str) -> TuiSettings:
    """
    Convert one provider target to TUI settings for auth and fetch.

    Args:
        target (ProviderTarget): Selected provider target.
        clone_protocol (str): Clone protocol default.

    Returns:
        TuiSettings: Single-provider settings.
    """
    return selected_targets_to_settings([target], clone_protocol=clone_protocol)


def split_csv(value: str | None) -> list[str] | None:
    """Split comma-separated text into normalized values."""
    if value is None:
        return None
    items = [item.strip() for item in value.split(",")]
    normalized = [item for item in items if item]
    return normalized or None


def _normalize_list_value(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return split_csv(value)
    if isinstance(value, list):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized or None
    raise ValueError("Quick default list values must be strings or lists.")


def _parse_optional_bool(value: Any, key: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"Invalid interactive.quick_defaults.{key} value '{value}'.")


def _parse_optional_int(value: Any, key: str) -> int | None:
    if value in {None, ""}:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as ex:
        raise ValueError(
            f"Invalid interactive.quick_defaults.{key} value '{value}'."
        ) from ex
    if parsed < 1:
        raise ValueError(
            f"Invalid interactive.quick_defaults.{key}; use 1 or higher."
        )
    return parsed


def load_quick_defaults(config_data: dict[str, Any]) -> TuiQuickDefaults:
    """
    Load non-secret quick wizard defaults from config data.

    Args:
        config_data (dict[str, Any]): Parsed YAML config.

    Returns:
        TuiQuickDefaults: Parsed quick defaults.
    """
    interactive = config_data.get("interactive") or {}
    if not isinstance(interactive, dict):
        raise ValueError("YAML config 'interactive' must be a mapping.")
    quick_defaults = interactive.get("quick_defaults") or {}
    if not isinstance(quick_defaults, dict):
        raise ValueError(
            "YAML config 'interactive.quick_defaults' must be a mapping."
        )

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
        since=_parse_date(str(quick_defaults.get("since") or "")),
        until=_parse_date(str(quick_defaults.get("until") or "")),
        interval=interval,
        author_name=_normalize_list_value(quick_defaults.get("author_name")),
        lang=_normalize_list_value(quick_defaults.get("lang")),
        exclude_dirs=_normalize_list_value(quick_defaults.get("exclude_dirs")),
        exclude_template_mode=exclude_template_mode,
        exclude_template_names=_normalize_list_value(
            quick_defaults.get("exclude_template_names")
        ),
        exclude_template_files=_normalize_list_value(
            quick_defaults.get("exclude_template_files")
        ),
        workers=_parse_optional_int(quick_defaults.get("workers"), "workers"),
        output=Path(quick_defaults["output"]) if quick_defaults.get("output") else None,
        cache_policy=cache_policy,
        no_plot_show=_parse_optional_bool(
            quick_defaults.get("no_plot_show"),
            "no_plot_show",
        ),
    )


def format_optional_list(value: list[str] | None) -> str:
    """Format an optional list for prompts and review text."""
    return ", ".join(value) if value else "(none)"


def format_compact_list(value: list[str] | None, *, limit: int = 5) -> str:
    """
    Format a list with a compact overflow marker.

    Args:
        value (list[str] | None): Values to format.
        limit (int): Number of values to show before compacting.

    Returns:
        str: Compact display text.
    """
    if not value:
        return "(none)"
    visible = value[:limit]
    suffix = ""
    remaining = len(value) - len(visible)
    if remaining > 0:
        suffix = f" (+{remaining} more)"
    return ", ".join(visible) + suffix


def _prompt_list_default(value: list[str] | None) -> str:
    return ", ".join(value) if value else ""


def _prompt(text: str, default: str | None = None) -> str:
    try:
        from prompt_toolkit import prompt
    except ImportError as ex:
        raise RuntimeError(
            "prompt_toolkit is required for interactive runs. "
            "Install dependencies with `uv sync --active`."
        ) from ex
    suffix = f" [{default}]" if default not in {None, ""} else ""
    raw = prompt(f"{text}{suffix}: ").strip()
    return raw if raw else (default or "")


def _prompt_bool(text: str, default: bool) -> bool:
    default_text = "y" if default else "n"
    while True:
        raw = _prompt(f"{text} (y/n)", default_text).casefold()
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print(tr("tui.enter_yes_no"))


def _prompt_provider_selection(settings: TuiSettings) -> list[ProviderTarget]:
    candidates = build_provider_candidates(settings)
    enabled_defaults = {target.key for target in build_provider_targets(settings)}
    selected: list[ProviderTarget] = []

    print()
    print(tr("tui.provider_selection"))
    for target in candidates:
        default = target.key in enabled_defaults
        if _prompt_bool(tr("tui.use_provider", label=target.label), default):
            base_url = target.base_url
            if target.key == "gitlab.self_hosted":
                base_url = _prompt(tr("tui.self_hosted_gitlab_base_url"), base_url)
                if not base_url:
                    raise ValueError(tr("tui.self_hosted_gitlab_base_url_required"))
            selected.append(
                ProviderTarget(
                    key=target.key,
                    provider=target.provider,
                    label=target.label,
                    base_url=base_url.rstrip("/"),
                )
            )
    if not selected:
        raise ValueError(tr("tui.provider_required"))
    return selected


def _parse_date(value: str) -> datetime | None:
    if not value.strip():
        return None
    return datetime.fromisoformat(value.strip())


def _format_date(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.date().isoformat()


def determine_cache_status(
    ref: RemoteRepositoryRef,
    *,
    clone_protocol: str,
    output: Path,
    repo_manager: RemoteRepoManager | None = None,
) -> str:
    """
    Return the lightweight cache status for a selected repository.

    Args:
        ref (RemoteRepositoryRef): Repository reference.
        clone_protocol (str): Selected clone protocol.
        output (Path): Output root containing `.cache`.
        repo_manager (RemoteRepoManager | None): Optional manager for tests.

    Returns:
        str: `cached`, `missing`, or `stale/invalid`.
    """
    cache_path = determine_cache_path(
        ref,
        clone_protocol=clone_protocol,
        output=output,
        repo_manager=repo_manager,
    )
    if not cache_path.exists():
        return "missing"
    if (cache_path / ".git").exists():
        return "cached"
    return "stale/invalid"


def determine_cache_path(
    ref: RemoteRepositoryRef,
    *,
    clone_protocol: str,
    output: Path,
    repo_manager: RemoteRepoManager | None = None,
) -> Path:
    """
    Return the cached clone path for a remote ref without creating it.

    Args:
        ref (RemoteRepositoryRef): Repository reference.
        clone_protocol (str): Selected clone protocol.
        output (Path): Output root containing `.cache`.
        repo_manager (RemoteRepoManager | None): Optional manager for tests.

    Returns:
        Path: Expected cached clone path.
    """
    repo_manager = repo_manager or RemoteRepoManager()
    return repo_manager._get_remote_cache_path(
        output / ".cache",
        ref.git_url(clone_protocol),
    )


DEFAULT_RECOMMENDED_EXCLUDES = [
    ".git",
    ".venv",
    "__pycache__",
    ".cache",
    "node_modules",
    "dist",
    "build",
    "out",
]


def _should_skip_scan_path(path: Path, root: Path) -> bool:
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in DEFAULT_RECOMMENDED_EXCLUDES for part in relative_parts)


def _scan_language_counts(root: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not root.exists() or not root.is_dir():
        return counts
    for file_path in root.rglob("*"):
        if not file_path.is_file() or _should_skip_scan_path(file_path, root):
            continue
        language = LanguageExtensions.get_language(file_path.name)
        if language != "Unknown":
            counts[language] += 1
    return counts


def build_lightweight_recommendations(
    state: TuiWizardState,
) -> LightweightRecommendations:
    """
    Build quick recommendations without cloning missing remote repositories.

    Args:
        state (TuiWizardState): Wizard state after repository selection.

    Returns:
        LightweightRecommendations: Language and path recommendations.
    """
    language_counts: Counter[str] = Counter()
    exclude_paths: list[str] = []
    detected_templates: list[str] = []
    templates = load_exclude_templates(state.exclude_template_files)
    for repository in state.selected_repositories:
        if repository.cache_status != "cached":
            continue
        cache_path = determine_cache_path(
            repository.ref,
            clone_protocol=state.clone_protocol,
            output=state.output,
        )
        if repository.include_subpath:
            cache_path = cache_path / repository.include_subpath
        language_counts.update(_scan_language_counts(cache_path))
        recommendation = build_exclude_recommendation(
            cache_path,
            manual_excludes=_combined_manual_excludes(state, repository),
            selected_template_names=(
                repository.exclude_template_names
                if repository.exclude_template_names is not None
                else state.exclude_template_names
            ),
            mode=repository.exclude_template_mode or state.exclude_template_mode,
            templates=templates,
        )
        exclude_paths.extend(recommendation.paths)
        detected_templates.extend(
            item.template.display_name for item in recommendation.detected_templates
        )

    languages = [
        language
        for language, _ in sorted(
            language_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    language_source = "existing cache" if languages else "not detected"
    return LightweightRecommendations(
        languages=languages,
        exclude_dirs=_deduplicate_text(exclude_paths),
        detected_templates=_deduplicate_text(detected_templates),
        language_source=language_source,
    )


def refresh_repository_cache_statuses(state: TuiWizardState) -> None:
    """
    Refresh lightweight cache status after output or protocol changes.

    Args:
        state (TuiWizardState): Wizard state to mutate.
    """
    for repository in state.selected_repositories:
        repository.cache_status = determine_cache_status(
            repository.ref,
            clone_protocol=state.clone_protocol,
            output=state.output,
        )


def _authenticate_provider_targets(
    targets: list[ProviderTarget],
    *,
    clone_protocol: str,
) -> tuple[dict[str, str], dict[str, str]]:
    tokens: dict[str, str] = {}
    labels: dict[str, str] = {}
    for target in targets:
        token_map, label_map = run_tui_auth_selection(
            target_to_settings(target, clone_protocol=clone_protocol),
            auto=True,
        )
        token = token_map.get(target.provider)
        if not token:
            raise ValueError(f"{target.label} authentication did not return a token.")
        tokens[target.key] = token
        labels[target.key] = label_map.get(target.provider, "")
    return tokens, labels


def _fetch_repository_catalog(
    targets: list[ProviderTarget],
    auth_tokens: dict[str, str],
) -> list[RemoteRepositoryRef]:
    catalog: list[RemoteRepositoryRef] = []
    for target in targets:
        token = auth_tokens.get(target.key)
        if not token:
            raise ValueError(f"{target.label} authentication token is missing.")
        try:
            if target.provider == "github":
                catalog.extend(
                    fetch_github_repositories(
                        api_base_url=target.base_url,
                        token=token,
                    )
                )
            elif target.provider == "gitlab":
                catalog.extend(
                    fetch_gitlab_repositories(
                        base_url=target.base_url,
                        token=token,
                    )
                )
            else:
                raise ValueError(f"Unsupported provider '{target.provider}'.")
        except OSError as ex:
            raise RemoteCatalogError(
                f"Failed to fetch {target.label} repositories: {ex}"
            ) from ex
    if not catalog:
        raise ValueError("No repositories were returned by selected providers.")
    return sorted(catalog, key=lambda ref: (ref.provider, ref.full_name.lower()))


def _build_branch_loader(
    targets: list[ProviderTarget],
    auth_tokens: dict[str, str],
):
    """Build a lazy branch loader for the two-pane repository selector."""
    targets_by_identity = {
        (target.provider, target.base_url.rstrip("/")): target for target in targets
    }
    targets_by_provider = {target.provider: target for target in targets}

    def load_branches(ref: RemoteRepositoryRef) -> list[str]:
        target = targets_by_identity.get(
            (ref.provider, ref.provider_base_url.rstrip("/"))
        )
        if target is None:
            target = targets_by_provider.get(ref.provider)
        if target is None:
            raise RemoteCatalogError(f"No provider target is available for {ref.provider}.")
        token = auth_tokens.get(target.key)
        if not token:
            raise RemoteCatalogError(f"{target.label} authentication token is missing.")
        try:
            if ref.provider == "github":
                return fetch_github_branches(
                    api_base_url=target.base_url,
                    full_name=ref.full_name,
                    token=token,
                )
            if ref.provider == "gitlab":
                return fetch_gitlab_branches(
                    base_url=target.base_url,
                    full_name=ref.full_name,
                    token=token,
                )
        except OSError as ex:
            raise RemoteCatalogError(
                f"Failed to fetch branches for {ref.full_name}: {ex}"
            ) from ex
        raise RemoteCatalogError(f"Unsupported provider '{ref.provider}'.")

    return load_branches


def build_initial_wizard_state(
    *,
    args: argparse.Namespace,
    settings: TuiSettings,
    provider_targets: list[ProviderTarget] | None = None,
    auth_tokens: dict[str, str],
    auth_labels: dict[str, str] | None = None,
    repository_catalog: list[RemoteRepositoryRef],
    selected_refs: list[RemoteRepositoryRef],
    selected_branches: dict[str, str] | None = None,
) -> TuiWizardState:
    """
    Build the initial wizard state from CLI/config defaults and selected repos.

    Args:
        args (argparse.Namespace): Parsed and config-merged CLI arguments.
        settings (TuiSettings): Loaded TUI settings.
        auth_tokens (dict[str, str]): Runtime provider tokens.
        repository_catalog (list[RemoteRepositoryRef]): Fetched repository catalog.
        selected_refs (list[RemoteRepositoryRef]): Repositories selected by the user.
        selected_branches (dict[str, str] | None): Branch choices keyed by repo full name.

    Returns:
        TuiWizardState: Initial state ready for interactive refinement.
    """
    output = args.output if isinstance(args.output, Path) else Path(args.output)
    clone_protocol = settings.defaults.clone_protocol
    global_excludes = list(args.exclude_dirs or [])
    selected_branches = selected_branches or {}
    selected_configs = [
        SelectedRepositoryConfig(
            ref=ref,
            branch=selected_branches.get(ref.full_name) or ref.default_branch or "main",
            cache_status=determine_cache_status(
                ref,
                clone_protocol=clone_protocol,
                output=output,
            ),
            exclude_dirs=[],
        )
        for ref in selected_refs
    ]
    state = TuiWizardState(
        provider_targets=provider_targets or build_provider_targets(settings),
        auth_tokens=auth_tokens,
        repository_catalog=repository_catalog,
        selected_repositories=selected_configs,
        auth_labels=auth_labels or {},
        clone_protocol=clone_protocol,
        since=args.since,
        until=args.until,
        interval=args.interval or "monthly",
        author_name=list(args.author_name) if args.author_name else None,
        lang=list(args.lang) if args.lang else None,
        workers=args.workers,
        global_exclude_dirs=global_excludes or None,
        output=output,
        clear_cache=bool(args.clear_cache),
        no_plot_show=True if args.no_plot_show is None else bool(args.no_plot_show),
    )
    state.recommendations = build_lightweight_recommendations(state)
    return state


def apply_quick_defaults(
    state: TuiWizardState,
    defaults: TuiQuickDefaults,
) -> None:
    """
    Apply non-secret quick defaults to a wizard state.

    Args:
        state (TuiWizardState): Wizard state to mutate.
        defaults (TuiQuickDefaults): Defaults from config.
    """
    if defaults.since is not None:
        state.since = defaults.since
    if defaults.until is not None:
        state.until = defaults.until
    if defaults.interval is not None:
        state.interval = defaults.interval
    if defaults.author_name is not None:
        state.author_name = defaults.author_name
    if defaults.lang is not None:
        state.lang = defaults.lang
    if defaults.exclude_dirs is not None:
        state.global_exclude_dirs = defaults.exclude_dirs
    if defaults.exclude_template_mode is not None:
        state.exclude_template_mode = defaults.exclude_template_mode
    if defaults.exclude_template_names is not None:
        state.exclude_template_names = defaults.exclude_template_names
    if defaults.exclude_template_files is not None:
        state.exclude_template_files = defaults.exclude_template_files
    if defaults.workers is not None:
        state.workers = defaults.workers
    if defaults.output is not None:
        state.output = defaults.output
    if defaults.cache_policy is not None:
        state.clear_cache = defaults.cache_policy == "clear"
        state.refresh_remote_cache_only = defaults.cache_policy == "update"
    if defaults.no_plot_show is not None:
        state.no_plot_show = defaults.no_plot_show
    refresh_repository_cache_statuses(state)


def apply_branch_selection(state: TuiWizardState, branch_override: str | None) -> None:
    """
    Apply a bulk branch override to selected repositories.

    Args:
        state (TuiWizardState): Wizard state to mutate.
        branch_override (str | None): Branch name, `default`, or None.
    """
    if branch_override is None:
        return
    normalized = branch_override.strip()
    if not normalized or normalized == "default":
        return
    for repository in state.selected_repositories:
        repository.branch = normalized


def apply_repository_overrides(
    state: TuiWizardState,
    overrides: dict[str, dict[str, Any]],
) -> None:
    """
    Apply per-repository branch, include path, and exclude path overrides.

    Args:
        state (TuiWizardState): Wizard state to mutate.
        overrides (dict[str, dict[str, Any]]): Overrides keyed by full repo name.
    """
    for repository in state.selected_repositories:
        override = overrides.get(repository.ref.full_name, {})
        branch = str(override.get("branch") or "").strip()
        if branch:
            repository.branch = branch
        include_subpath = str(override.get("include_subpath") or "").strip()
        repository.include_subpath = include_subpath or repository.include_subpath
        exclude_dirs = override.get("exclude_dirs")
        if exclude_dirs is not None:
            if isinstance(exclude_dirs, str):
                repository.exclude_dirs = split_csv(exclude_dirs) or []
            else:
                repository.exclude_dirs = [
                    str(item).strip()
                    for item in exclude_dirs
                    if str(item).strip()
                ]
        exclude_template_mode = override.get("exclude_template_mode")
        if exclude_template_mode is not None:
            repository.exclude_template_mode = normalize_exclude_template_mode(
                exclude_template_mode
            )
        exclude_template_names = override.get("exclude_template_names")
        if exclude_template_names is not None:
            repository.exclude_template_names = _normalize_list_value(
                exclude_template_names
            )


def _prompt_branch_selection(state: TuiWizardState) -> None:
    print()
    print(tr("tui.branch_selection"))
    branch = _prompt(tr("tui.bulk_branch"), "")
    apply_branch_selection(state, branch or None)
    if not _prompt_bool(tr("tui.edit_individual_repos"), False):
        return
    for repository in state.selected_repositories:
        branch = _prompt(
            tr("tui.repo_branch_prompt", repo=repository.ref.full_name),
            repository.branch,
        )
        repository.branch = branch or repository.branch
        include_subpath = _prompt(
            tr("tui.include_subpath_prompt", repo=repository.ref.full_name),
            repository.include_subpath or "",
        )
        repository.include_subpath = include_subpath or None
        exclude_dirs = _prompt(
            tr("tui.repo_excludes_prompt", repo=repository.ref.full_name),
            ", ".join(repository.exclude_dirs),
        )
        repository.exclude_dirs = split_csv(exclude_dirs) or []


def _prompt_analysis_scope(state: TuiWizardState) -> None:
    print()
    print(tr("tui.analysis_scope"))
    state.since = _parse_date(_prompt(tr("tui.since_prompt"), _format_date(state.since)))
    state.until = _parse_date(_prompt(tr("tui.until_prompt"), _format_date(state.until)))
    state.interval = _prompt(tr("tui.interval_prompt"), state.interval)
    if state.interval not in {"daily", "weekly", "monthly"}:
        raise ValueError(tr("tui.interval_error"))
    state.author_name = split_csv(_prompt(tr("tui.author_filter"), _prompt_list_default(state.author_name)))
    state.lang = split_csv(_prompt(tr("tui.language_filter"), _prompt_list_default(state.lang)))
    workers = _prompt(
        tr("tui.workers_prompt"),
        "" if state.workers is None else str(state.workers),
    )
    state.workers = int(workers) if workers else None
    if state.workers is not None and state.workers < 1:
        raise ValueError(tr("tui.workers_error"))


def _prompt_path_rules(state: TuiWizardState) -> None:
    print()
    print(tr("tui.path_rules"))
    state.exclude_template_mode = normalize_exclude_template_mode(
        _prompt("Exclude template mode (auto/manual/off)", state.exclude_template_mode)
    )
    templates = load_exclude_templates(state.exclude_template_files)
    template_names = ", ".join(template.name for template in templates)
    selected_default = ", ".join(state.exclude_template_names or [])
    selected_templates = _prompt(
        f"Exclude templates to force [blank=auto-detect; available: {template_names}]",
        selected_default,
    )
    state.exclude_template_names = split_csv(selected_templates) or None
    state.global_exclude_dirs = split_csv(
        _prompt(tr("tui.global_excludes_prompt"), _prompt_list_default(state.global_exclude_dirs))
    )
    state.recommendations = build_lightweight_recommendations(state)
    if state.recommendations.detected_templates:
        print("Detected exclude templates:")
        for template_name in state.recommendations.detected_templates:
            print(f"- [x] {template_name}")
    if state.recommendations.exclude_dirs:
        print("Recommended excludes: " + format_compact_list(state.recommendations.exclude_dirs))
    if not _prompt_bool(tr("tui.edit_per_repo_paths"), False):
        return
    for repository in state.selected_repositories:
        include_subpath = _prompt(
            tr("tui.include_subpath_prompt", repo=repository.ref.full_name),
            repository.include_subpath or "",
        )
        repository.include_subpath = include_subpath or None
        repo_mode = _prompt(
            f"Exclude template mode for {repository.ref.full_name} [blank=global]",
            repository.exclude_template_mode or "",
        )
        repository.exclude_template_mode = repo_mode or None
        repo_template_names = _prompt(
            f"Exclude templates for {repository.ref.full_name} [blank=global/auto]",
            ", ".join(repository.exclude_template_names or []),
        )
        repository.exclude_template_names = split_csv(repo_template_names) or None
        exclude_dirs = _prompt(
            tr("tui.repo_extra_excludes_prompt", repo=repository.ref.full_name),
            ", ".join(repository.exclude_dirs),
        )
        repository.exclude_dirs = split_csv(exclude_dirs) or []
    state.recommendations = build_lightweight_recommendations(state)


def _prompt_output_cache_display(state: TuiWizardState) -> None:
    print()
    print(tr("tui.output_cache_display"))
    state.output = Path(_prompt(tr("tui.output_directory"), str(state.output)))
    cache_choice = _prompt(
        tr("tui.cache_policy_prompt"),
        "clear" if state.clear_cache else "use",
    ).casefold()
    if cache_choice not in {"use", "update", "clear"}:
        raise ValueError(tr("tui.cache_policy_error"))
    state.clear_cache = cache_choice == "clear"
    state.refresh_remote_cache_only = cache_choice == "update"
    state.no_plot_show = not _prompt_bool(tr("tui.auto_display_prompt"), False)


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


def render_final_review(
    state: TuiWizardState,
    *,
    color: bool = False,
    detailed: bool = False,
) -> str:
    """
    Render the final wizard review.

    Args:
        state (TuiWizardState): Wizard state to render.

    Returns:
        str: Human-readable final review.
    """
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
        "",
        _color(tr("tui.repositories"), Fore.CYAN, enabled=color),
    ]
    for repository in state.selected_repositories:
        include = repository.include_subpath or "."
        excludes = _combined_excludes(state, repository)
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


def _combined_excludes(
    state: TuiWizardState,
    repository: SelectedRepositoryConfig,
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


def _filter_present_excludes(
    state: TuiWizardState,
    repository: SelectedRepositoryConfig,
    excludes: list[str] | None,
) -> list[str]:
    """Return selected excludes without dropping template paths that are absent now."""
    return excludes or []


def apply_wizard_state(args: argparse.Namespace, state: TuiWizardState) -> argparse.Namespace:
    """
    Apply confirmed wizard state to parsed CLI arguments.

    Args:
        args (argparse.Namespace): Parsed CLI args.
        state (TuiWizardState): Confirmed wizard state.

    Returns:
        argparse.Namespace: The same namespace updated in place.
    """
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
    """
    Convert wizard state to a non-secret YAML configuration mapping.

    Args:
        state (TuiWizardState): Confirmed wizard state.

    Returns:
        dict[str, Any]: YAML-safe config data without authentication tokens.
    """
    providers: dict[str, Any] = {}
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
    """
    Save non-secret wizard settings to YAML.

    Args:
        path (Path): Destination path.
        state (TuiWizardState): Confirmed wizard state.
    """
    path.write_text(
        yaml.safe_dump(wizard_state_to_config(state), sort_keys=False),
        encoding="utf-8",
    )


def normalize_final_action(raw: str) -> str | None:
    """Normalize final review action input into an action name."""
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
        "save+run": "save",
        "c": "cancel",
        "cancel": "cancel",
    }
    return aliases.get(value)


def _prompt_final_action(state: TuiWizardState) -> str:
    detailed = False
    while True:
        print()
        print(render_final_review(state, color=True, detailed=detailed))
        raw = _prompt(tr("tui.action"), "")
        action = normalize_final_action(raw)
        if action == "details":
            detailed = True
            continue
        if action in {"run", "edit", "cancel", "save"}:
            return action
        print(tr("tui.choose_action"))


def _prompt_edit_category() -> str:
    print()
    print(_color(tr("tui.edit_settings"), Fore.CYAN + Style.BRIGHT, enabled=True))
    print(f"1. {tr('tui.category.repositories')}")
    print(f"2. {tr('tui.category.analysis')}")
    print(f"3. {tr('tui.category.paths')}")
    print(f"4. {tr('tui.category.output')}")
    print(f"5. {tr('tui.category.providers')}")
    print(f"6. {tr('tui.category.done')}")
    while True:
        choice = _prompt(tr("tui.select_category"), "6").casefold()
        category_map = {
            "1": "repositories",
            "repositories": "repositories",
            "branches": "repositories",
            "2": "analysis",
            "analysis": "analysis",
            "scope": "analysis",
            "3": "paths",
            "path": "paths",
            "paths": "paths",
            "4": "output",
            "cache": "output",
            "display": "output",
            "output": "output",
            "5": "providers",
            "provider": "providers",
            "providers": "providers",
            "6": "done",
            "done": "done",
            "back": "done",
        }
        category = category_map.get(choice)
        if category is not None:
            return category
        print(tr("tui.choose_category"))


def _run_wizard_steps(state: TuiWizardState) -> str:
    while True:
        action = _prompt_final_action(state)
        if action != "edit":
            return action
        while True:
            category = _prompt_edit_category()
            if category == "done":
                break
            if category == "repositories":
                _prompt_branch_selection(state)
            elif category == "analysis":
                _prompt_analysis_scope(state)
            elif category == "paths":
                _prompt_path_rules(state)
            elif category == "output":
                _prompt_output_cache_display(state)
                state.recommendations = build_lightweight_recommendations(state)
            elif category == "providers":
                print(tr("tui.provider_restart"))


def run_tui_wizard(
    args: argparse.Namespace,
    config_data: dict[str, Any],
) -> argparse.Namespace:
    """
    Run the full interactive flow and apply confirmed settings to CLI args.

    Args:
        args (argparse.Namespace): Parsed CLI arguments.
        config_data (dict[str, Any]): Parsed YAML config.

    Returns:
        argparse.Namespace: Updated CLI args.
    """
    just_fix_windows_console()
    settings = load_tui_settings(config_data)
    quick_defaults = load_quick_defaults(config_data)
    provider_targets = choose_auto_provider_targets(settings)
    if provider_targets is None:
        provider_targets = _prompt_provider_selection(settings)
    auth_tokens, auth_labels = _authenticate_provider_targets(
        provider_targets,
        clone_protocol=settings.defaults.clone_protocol,
    )
    repository_catalog = _fetch_repository_catalog(provider_targets, auth_tokens)
    selection_result = run_repository_selector(
        repository_catalog,
        branch_loader=_build_branch_loader(provider_targets, auth_tokens),
        return_result=True,
    )
    if isinstance(selection_result, RepositorySelectionResult):
        selected_refs = selection_result.selected_refs
        selected_branches = selection_result.selected_branches
    else:
        selected_refs = selection_result
        selected_branches = {}
    state = build_initial_wizard_state(
        args=args,
        settings=settings,
        provider_targets=provider_targets,
        auth_tokens=auth_tokens,
        auth_labels=auth_labels,
        repository_catalog=repository_catalog,
        selected_refs=selected_refs,
        selected_branches=selected_branches,
    )
    apply_quick_defaults(state, quick_defaults)
    state.recommendations = build_lightweight_recommendations(state)
    action = _run_wizard_steps(state)
    if action == "cancel":
        from analyze_git_repo_loc.tui_selector import TuiSelectionCancelled

        raise TuiSelectionCancelled("Interactive run cancelled.")
    if action == "save":
        save_wizard_config(args.config, state)
    return apply_wizard_state(args, state)
