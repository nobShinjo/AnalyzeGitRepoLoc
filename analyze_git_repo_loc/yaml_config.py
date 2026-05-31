"""
YAML configuration loader and merger for CLI arguments.

Functions:
    load_yaml_data
    load_yaml_config
    merge_yaml_config

Overview:
    Loads the YAML configuration structure for multiple repositories and merges
    settings into parsed CLI arguments with CLI precedence.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import yaml

from analyze_git_repo_loc.remote_auth import build_host_provider_env_var
from analyze_git_repo_loc.remote_repos import RemoteRepoManager


def load_yaml_data(config_path: Path) -> dict:
    """
    Load YAML configuration data and validate the top-level shape.

    Args:
        config_path (Path): Path to the YAML configuration file.

    Returns:
        dict: Parsed YAML mapping.
    """
    if not config_path.exists():
        raise ValueError(f"Config file not found: {config_path}")
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as ex:
        raise ValueError(f"Invalid YAML in config file: {config_path}") from ex
    if not isinstance(data, dict):
        raise ValueError("YAML config must be a mapping at the top level.")
    return data


def load_yaml_config(
    config_path: Path,
    *,
    require_repositories: bool = True,
) -> tuple[dict, list[dict]]:
    """
    Load YAML configuration data and validate required structure.

    Args:
        config_path (Path): Path to the YAML configuration file.
        require_repositories (bool): Whether repositories must be present.

    Returns:
        tuple[dict, list[dict]]: (settings, repositories) dictionaries.
    """
    data = load_yaml_data(config_path)

    settings = data.get("settings") or {}
    if not isinstance(settings, dict):
        raise ValueError("YAML config 'settings' must be a mapping.")

    repositories = data.get("repositories")
    if repositories is None and not require_repositories:
        repositories = []
    if not isinstance(repositories, list) or not repositories:
        if not require_repositories and repositories == []:
            return settings, []
        raise ValueError("YAML config 'repositories' must be a non-empty list.")
    normalized_repositories: list[dict] = []
    for entry in repositories:
        repository = entry
        if isinstance(repository, str):
            repository = {"path": repository}
        if not isinstance(repository, dict):
            raise ValueError("YAML config repository entry must be a mapping.")
        if not repository.get("path"):
            raise ValueError("YAML config repository entry requires 'path'.")
        normalized_repositories.append(repository)

    return settings, normalized_repositories


def _pick_value(args: argparse.Namespace, settings: dict, key: str):
    cli_value = getattr(args, key)
    if cli_value is not None:
        return cli_value
    return settings.get(key)


def _resolve_output_path(output_value) -> Path:
    if output_value is None:
        return Path("./out")
    return output_value if isinstance(output_value, Path) else Path(output_value)


def _resolve_interval(interval_value) -> str:
    interval = interval_value or "monthly"
    if interval not in {"daily", "weekly", "monthly"}:
        raise ValueError(f"Invalid interval: {interval}")
    return interval


def _resolve_workers(workers_value) -> int | None:
    if workers_value is None:
        return None
    if isinstance(workers_value, str):
        workers_value = workers_value.strip()
        if not workers_value:
            return None
    try:
        workers = int(workers_value)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"Invalid workers value '{workers_value}'.") from ex
    if workers < 1:
        raise ValueError(f"Invalid workers value '{workers_value}'. Use 1 or higher.")
    return workers


def _resolve_optional_bool(bool_value, key: str) -> bool | None:
    if bool_value is None:
        return None
    if isinstance(bool_value, bool):
        return bool_value
    if isinstance(bool_value, str):
        normalized = bool_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"Invalid {key} value '{bool_value}'.")


def _build_repo_entries(
    repositories: list[dict],
    repo_manager: RemoteRepoManager,
    normalize_list: Callable[[list[str] | str | None], list[str] | None],
) -> list[tuple[Path | str, str, list[str], str | None, str | None, list[str] | None]]:
    repo_entries = []
    for repository in repositories:
        repo_path_value = repository["path"]
        branch_name = repository.get("branch") or "main"
        exclude_dirs = normalize_list(repository.get("exclude_dirs")) or []
        include_subpath = repository.get("include_subpath")
        exclude_template_mode = repository.get("exclude_template_mode")
        if exclude_template_mode is not None:
            exclude_template_mode = str(exclude_template_mode).strip() or None
        exclude_template_names = normalize_list(repository.get("exclude_template_names"))
        if include_subpath is not None:
            include_subpath = str(include_subpath).strip() or None
        repo_path = (
            repo_path_value
            if repo_manager.is_git_url(repo_path_value)
            else Path(repo_path_value)
        )
        if exclude_template_mode is not None or exclude_template_names is not None:
            repo_entries.append(
                (
                    repo_path,
                    branch_name,
                    exclude_dirs,
                    include_subpath,
                    exclude_template_mode,
                    exclude_template_names,
                )
            )
        else:
            repo_entries.append((repo_path, branch_name, exclude_dirs, include_subpath))
    return repo_entries


def _apply_config_provider_hints(config_data: dict) -> None:
    """Restore provider hints for configured self-hosted interactive providers."""
    interactive = config_data.get("interactive")
    if not isinstance(interactive, dict):
        return
    providers = interactive.get("providers")
    if not isinstance(providers, dict):
        return

    github = providers.get("github")
    if isinstance(github, dict) and github.get("enabled"):
        parsed = urlparse(str(github.get("api_base_url") or "https://api.github.com"))
        if parsed.hostname and parsed.hostname != "api.github.com":
            os.environ[build_host_provider_env_var(parsed.hostname)] = "github"

    gitlab = providers.get("gitlab")
    if isinstance(gitlab, dict) and gitlab.get("enabled"):
        parsed = urlparse(str(gitlab.get("base_url") or "https://gitlab.com"))
        if parsed.hostname and parsed.hostname != "gitlab.com":
            os.environ[build_host_provider_env_var(parsed.hostname)] = "gitlab"


def merge_yaml_config(
    args: argparse.Namespace,
    repo_manager: RemoteRepoManager,
    normalize_list: Callable[[list[str] | str | None], list[str] | None],
) -> argparse.Namespace:
    """
    Merge YAML config values into CLI arguments with CLI precedence.

    Args:
        args (argparse.Namespace): Parsed CLI arguments.
        repo_manager (RemoteRepoManager): Helper for URL detection.
        normalize_list (Callable): Normalizer for list-like inputs.

    Returns:
        argparse.Namespace: Updated arguments with YAML config applied.
    """
    config_data = load_yaml_data(args.config)
    _apply_config_provider_hints(config_data)
    settings, repositories = load_yaml_config(
        args.config,
        require_repositories=not getattr(args, "interactive", False),
    )

    args.output = _resolve_output_path(_pick_value(args, settings, "output"))
    args.interval = _resolve_interval(_pick_value(args, settings, "interval"))
    args.since = _pick_value(args, settings, "since")
    args.until = _pick_value(args, settings, "until")
    args.lang = _pick_value(args, settings, "lang")
    args.author_name = _pick_value(args, settings, "author_name")
    args.exclude_dirs = _pick_value(args, settings, "exclude_dirs")
    args.exclude_template_mode = settings.get("exclude_template_mode", "auto")
    args.exclude_template_names = normalize_list(settings.get("exclude_template_names"))
    args.exclude_template_files = normalize_list(settings.get("exclude_template_files"))
    args.workers = _resolve_workers(_pick_value(args, settings, "workers"))
    args.clear_cache = _resolve_optional_bool(
        _pick_value(args, settings, "clear_cache"),
        "clear_cache",
    )
    args.no_plot_show = _resolve_optional_bool(
        _pick_value(args, settings, "no_plot_show"),
        "no_plot_show",
    )

    if args.repo_paths is None and repositories:
        args.repo_paths = _build_repo_entries(
            repositories,
            repo_manager,
            normalize_list,
        )

    return args
