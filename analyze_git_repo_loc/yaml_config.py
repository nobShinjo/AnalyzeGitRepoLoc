"""
YAML configuration loader and merger for CLI arguments.

Functions:
    load_yaml_config
    merge_yaml_config

Overview:
    Loads the YAML configuration structure and merges settings into parsed CLI
    arguments with CLI precedence.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Callable

import yaml

from analyze_git_repo_loc.remote_repos import RemoteRepoManager


def load_yaml_config(config_path: Path) -> tuple[dict, dict]:
    """
    Load YAML configuration data and validate required structure.

    Args:
        config_path (Path): Path to the YAML configuration file.

    Returns:
        tuple[dict, dict]: (settings, repository) dictionaries.
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

    settings = data.get("settings") or {}
    if not isinstance(settings, dict):
        raise ValueError("YAML config 'settings' must be a mapping.")

    repositories = data.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise ValueError("YAML config 'repositories' must be a non-empty list.")
    if len(repositories) != 1:
        raise ValueError("YAML config currently supports a single repository entry.")

    repository = repositories[0]
    if isinstance(repository, str):
        repository = {"path": repository}
    if not isinstance(repository, dict):
        raise ValueError("YAML config repository entry must be a mapping.")
    if not repository.get("path"):
        raise ValueError("YAML config repository entry requires 'path'.")

    return settings, repository


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
    settings, repository = load_yaml_config(args.config)

    def _pick_value(key: str):
        cli_value = getattr(args, key)
        if cli_value is not None:
            return cli_value
        if key in repository and repository[key] is not None:
            return repository[key]
        return settings.get(key)

    output_value = _pick_value("output")
    if output_value is None:
        args.output = Path("./out")
    else:
        args.output = output_value if isinstance(output_value, Path) else Path(output_value)

    interval_value = _pick_value("interval")
    args.interval = interval_value or "monthly"
    if args.interval not in {"daily", "weekly", "monthly"}:
        raise ValueError(f"Invalid interval: {args.interval}")

    args.since = _pick_value("since")
    args.until = _pick_value("until")
    args.lang = _pick_value("lang")
    args.author_name = _pick_value("author_name")
    args.exclude_dirs = _pick_value("exclude_dirs")

    if args.repo_paths is None:
        repo_path_value = repository["path"]
        branch_name = repository.get("branch") or "main"
        exclude_dirs = normalize_list(repository.get("exclude_dirs"))
        repo_path = (
            repo_path_value
            if repo_manager.is_git_url(repo_path_value)
            else Path(repo_path_value)
        )
        args.repo_paths = [(repo_path, branch_name, exclude_dirs or [])]

    return args
