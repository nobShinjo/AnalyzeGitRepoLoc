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
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from colorama import Fore, Style, just_fix_windows_console

from analyze_git_repo_loc.analysis.exclude_templates import (
    build_exclude_recommendation,
    load_exclude_templates,
    normalize_exclude_template_mode,
)
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.interactive.tui_auth import run_tui_auth_selection
from analyze_git_repo_loc.interactive.tui_config import (
    apply_wizard_state as _apply_wizard_state_impl,
)
from analyze_git_repo_loc.interactive.tui_config import (
    save_wizard_config as _save_wizard_config_impl,
)
from analyze_git_repo_loc.interactive.tui_config import (
    wizard_state_to_config as _wizard_state_to_config_impl,
)
from analyze_git_repo_loc.interactive.tui_review import (
    format_compact_list as _format_compact_list_impl,
)
from analyze_git_repo_loc.interactive.tui_review import (
    format_optional_list as _format_optional_list_impl,
)
from analyze_git_repo_loc.interactive.tui_review import (
    render_final_review as _render_final_review_impl,
)
from analyze_git_repo_loc.interactive.tui_selector import (
    RepositorySelectionResult,
    run_repository_selector,
)
from analyze_git_repo_loc.interactive.tui_state import (
    LightweightRecommendations,
    ProviderTarget,
    SelectedRepositoryConfig,
    TuiQuickDefaults,
    TuiWizardState,
)
from analyze_git_repo_loc.interactive.tui_state import (
    load_quick_defaults as _load_quick_defaults_impl,
)
from analyze_git_repo_loc.language_extensions import LanguageExtensions
from analyze_git_repo_loc.remote.remote_catalog import (
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
from analyze_git_repo_loc.remote.remote_repos import RemoteRepoManager


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
        label = (
            GITLAB_DOT_COM_LABEL
            if base_url.rstrip("/") == GITLAB_DOT_COM_BASE_URL
            else "GitLab"
        )
        key = "gitlab.com" if label == GITLAB_DOT_COM_LABEL else GITLAB_SELF_HOSTED_KEY
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
            label=GITLAB_DOT_COM_LABEL,
            base_url=GITLAB_DOT_COM_BASE_URL,
        ),
        ProviderTarget(
            key=GITLAB_SELF_HOSTED_KEY,
            provider="gitlab",
            label="Self-hosted GitLab",
            base_url=(
                settings.providers.gitlab.base_url
                if settings.providers.gitlab.base_url.rstrip("/")
                != GITLAB_DOT_COM_BASE_URL
                else ""
            ),
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
                base_url=gitlab.base_url if gitlab else GITLAB_DOT_COM_BASE_URL,
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
        raise ValueError(f"Invalid interactive.quick_defaults.{key}; use 1 or higher.")
    return parsed


def load_quick_defaults(config_data: dict[str, Any]) -> TuiQuickDefaults:
    """Load non-secret quick wizard defaults from config data."""
    return _load_quick_defaults_impl(
        config_data,
        parse_date=_parse_date,
        normalize_list_value=_normalize_list_value,
        parse_optional_bool=_parse_optional_bool,
        parse_optional_int=_parse_optional_int,
        normalize_exclude_template_mode=normalize_exclude_template_mode,
    )


def format_optional_list(value: list[str] | None) -> str:
    """Format an optional list for prompts and review text."""
    return _format_optional_list_impl(value)


def format_compact_list(value: list[str] | None, *, limit: int = 5) -> str:
    """Format a list with a compact overflow marker."""
    return _format_compact_list_impl(value, limit=limit)


def _prompt_list_default(value: list[str] | None) -> str:
    return ", ".join(value) if value else ""


def _prompt(text: str, default: str | None = None) -> str:
    try:
        from prompt_toolkit import prompt  # pyright: ignore[reportMissingImports]
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
            if target.key == GITLAB_SELF_HOSTED_KEY:
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
    return repo_manager.get_remote_cache_path(
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
GITLAB_DOT_COM_LABEL = "GitLab.com"
GITLAB_DOT_COM_BASE_URL = "https://gitlab.com"
GITLAB_SELF_HOSTED_KEY = "gitlab.self_hosted"


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
            mode=normalize_exclude_template_mode(
                repository.exclude_template_mode or state.exclude_template_mode
            ),
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
            raise RemoteCatalogError(
                f"No provider target is available for {ref.provider}."
            )
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
        _apply_repository_override(
            repository,
            _find_repository_override(repository, overrides),
        )


def _repository_override_key(path_value: Any) -> str | None:
    """Normalize a repository config path to a provider-safe host/path key."""
    path_text = str(path_value or "").strip()
    if not path_text:
        return None
    if path_text.startswith("git@"):
        host_path = path_text.split("@", 1)[-1]
        if ":" not in host_path:
            return None
        host, repo_path = host_path.split(":", 1)
    else:
        parsed = urlparse(path_text)
        if not parsed.scheme or not parsed.hostname or not parsed.path:
            return None
        host = parsed.hostname
        repo_path = parsed.path
    normalized = repo_path.lstrip("/").rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    if not normalized:
        return None
    return f"{host.lower()}/{normalized}"


def _selected_repository_override_keys(
    repository: SelectedRepositoryConfig,
) -> list[str]:
    """Return supported override keys for a selected repository."""
    keys: list[str] = []
    for path_value in (repository.ref.clone_url, repository.ref.ssh_url):
        key = _repository_override_key(path_value)
        if key and key not in keys:
            keys.append(key)
    provider_key = f"{repository.ref.provider}:{repository.ref.full_name}"
    if provider_key not in keys:
        keys.append(provider_key)
    if repository.ref.full_name not in keys:
        keys.append(repository.ref.full_name)
    return keys


def load_repository_overrides(config_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract per-repository overrides from parsed YAML config data."""
    repositories = config_data.get("repositories")
    if not isinstance(repositories, list):
        return {}
    overrides: dict[str, dict[str, Any]] = {}
    for repository in repositories:
        if not isinstance(repository, dict):
            continue
        key = _repository_override_key(repository.get("path"))
        if not key:
            continue
        overrides[key] = {
            field: repository[field]
            for field in (
                "branch",
                "include_subpath",
                "exclude_dirs",
                "exclude_template_mode",
                "exclude_template_names",
            )
            if field in repository
        }
    return overrides


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
    state.since = _parse_date(
        _prompt(tr("tui.since_prompt"), _format_date(state.since))
    )
    state.until = _parse_date(
        _prompt(tr("tui.until_prompt"), _format_date(state.until))
    )
    state.interval = _prompt(tr("tui.interval_prompt"), state.interval)
    if state.interval not in {"daily", "weekly", "monthly"}:
        raise ValueError(tr("tui.interval_error"))
    state.author_name = split_csv(
        _prompt(tr("tui.author_filter"), _prompt_list_default(state.author_name))
    )
    state.lang = split_csv(
        _prompt(tr("tui.language_filter"), _prompt_list_default(state.lang))
    )
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
        _prompt(
            tr("tui.global_excludes_prompt"),
            _prompt_list_default(state.global_exclude_dirs),
        )
    )
    state.recommendations = build_lightweight_recommendations(state)
    if state.recommendations.detected_templates:
        print("Detected exclude templates:")
        for template_name in state.recommendations.detected_templates:
            print(f"- [x] {template_name}")
    if state.recommendations.exclude_dirs:
        print(
            "Recommended excludes: "
            + format_compact_list(state.recommendations.exclude_dirs)
        )
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


def _color(text: str, color: object, *, enabled: bool) -> str:
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
    """Render the final wizard review."""
    return _render_final_review_impl(
        state,
        determine_cache_path=determine_cache_path,
        color=color,
        detailed=detailed,
    )


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
        mode=normalize_exclude_template_mode(
            repository.exclude_template_mode or state.exclude_template_mode
        ),
        templates=load_exclude_templates(state.exclude_template_files),
    )
    return recommendation.paths or None


def _find_repository_override(
    repository: SelectedRepositoryConfig,
    overrides: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    for key in _selected_repository_override_keys(repository):
        override = overrides.get(key, {})
        if override:
            return override
    return {}


def _normalize_override_exclude_dirs(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return split_csv(value) or []
    return [str(item).strip() for item in value if str(item).strip()]


def _apply_repository_override(
    repository: SelectedRepositoryConfig,
    override: dict[str, Any],
) -> None:
    branch = str(override.get("branch") or "").strip()
    if branch:
        repository.branch = branch

    include_subpath = str(override.get("include_subpath") or "").strip()
    if include_subpath:
        repository.include_subpath = include_subpath

    exclude_dirs = _normalize_override_exclude_dirs(override.get("exclude_dirs"))
    if exclude_dirs is not None:
        repository.exclude_dirs = exclude_dirs

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


def _filter_present_excludes(
    excludes: list[str] | None,
) -> list[str]:
    """Return selected excludes without dropping template paths that are absent now."""
    return excludes or []


def apply_wizard_state(
    args: argparse.Namespace, state: TuiWizardState
) -> argparse.Namespace:
    """Apply confirmed wizard state to parsed CLI arguments."""
    return _apply_wizard_state_impl(args, state)


def wizard_state_to_config(state: TuiWizardState) -> dict[str, Any]:
    """Convert wizard state to a non-secret YAML configuration mapping."""
    return _wizard_state_to_config_impl(state)


def save_wizard_config(path: Path, state: TuiWizardState) -> None:
    """Save non-secret wizard settings to YAML."""
    _save_wizard_config_impl(path, state)


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
    repository_overrides = load_repository_overrides(config_data)
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
    apply_repository_overrides(state, repository_overrides)
    for repository in state.selected_repositories:
        selected_branch = selected_branches.get(repository.ref.full_name)
        if selected_branch:
            repository.branch = selected_branch
    state.recommendations = build_lightweight_recommendations(state)
    action = _run_wizard_steps(state)
    if action == "cancel":
        from analyze_git_repo_loc.interactive.tui_selector import TuiSelectionCancelled

        raise TuiSelectionCancelled("Interactive run cancelled.")
    if action == "save":
        save_wizard_config(args.config, state)
    return apply_wizard_state(args, state)
