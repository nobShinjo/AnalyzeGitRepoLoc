"""
Remote repository catalog loading for the TUI selector.

Description:
    Loads non-secret TUI settings, fetches GitHub/GitLab repository lists via
    standard-library HTTP calls, and normalizes provider responses into a common
    internal model.
Classes:
    RemoteCatalogError:
        Raised when TUI repository discovery cannot continue.
    RemoteRepositoryRef:
        Normalized reference to a remote repository.
    TuiSettings:
        Validated TUI provider and default settings.
Functions:
    load_tui_settings:
        Parse and validate the `tui` YAML section.
    fetch_remote_repositories:
        Fetch repositories from enabled providers.
    selected_refs_to_repo_paths:
        Convert selected refs into existing CLI repo tuple entries.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


class RemoteCatalogError(ValueError):
    """Repository catalog discovery failed."""


@dataclass(frozen=True)
class RemoteRepositoryRef:
    """Normalized reference to a GitHub or GitLab repository."""

    provider: str
    name: str
    full_name: str
    clone_url: str
    ssh_url: str
    web_url: str
    default_branch: str

    def git_url(self, clone_protocol: str) -> str:
        """
        Return the Git URL matching the requested clone protocol.

        Args:
            clone_protocol (str): `https` or `ssh`.

        Returns:
            str: Git URL for analysis.
        """
        if clone_protocol == "ssh" and self.ssh_url:
            return self.ssh_url
        return self.clone_url


@dataclass(frozen=True)
class GitHubProviderSettings:
    """GitHub TUI provider settings."""

    enabled: bool = False
    api_base_url: str = "https://api.github.com"


@dataclass(frozen=True)
class GitLabProviderSettings:
    """GitLab TUI provider settings."""

    enabled: bool = False
    base_url: str = "https://gitlab.com"


@dataclass(frozen=True)
class TuiProviderSettings:
    """All supported TUI provider settings."""

    github: GitHubProviderSettings
    gitlab: GitLabProviderSettings


@dataclass(frozen=True)
class TuiDefaults:
    """TUI defaults."""

    clone_protocol: str = "https"


@dataclass(frozen=True)
class TuiSettings:
    """Validated TUI settings."""

    providers: TuiProviderSettings
    defaults: TuiDefaults


def _require_mapping(value: Any, label: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RemoteCatalogError(f"YAML config '{label}' must be a mapping.")
    return value


def _read_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise RemoteCatalogError(f"Invalid boolean value '{value}'.")


def _read_text(value: Any, *, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise RemoteCatalogError(f"Invalid text value '{value}'.")
    normalized = value.strip()
    return normalized or default


def load_tui_settings(config_data: dict) -> TuiSettings:
    """
    Load and validate TUI settings from parsed YAML data.

    Args:
        config_data (dict): Parsed YAML mapping.

    Returns:
        TuiSettings: Validated settings with defaults.

    Raises:
        RemoteCatalogError: If the TUI configuration is invalid.
    """
    if not isinstance(config_data, dict):
        raise RemoteCatalogError("YAML config must be a mapping at the top level.")
    tui = _require_mapping(config_data.get("tui"), "tui")
    providers = _require_mapping(tui.get("providers"), "tui.providers")
    github = _require_mapping(providers.get("github"), "tui.providers.github")
    gitlab = _require_mapping(providers.get("gitlab"), "tui.providers.gitlab")
    defaults = _require_mapping(tui.get("defaults"), "tui.defaults")

    github_settings = GitHubProviderSettings(
        enabled=_read_bool(github.get("enabled"), default=False),
        api_base_url=_read_text(
            github.get("api_base_url"),
            default="https://api.github.com",
        ).rstrip("/"),
    )
    gitlab_settings = GitLabProviderSettings(
        enabled=_read_bool(gitlab.get("enabled"), default=False),
        base_url=_read_text(
            gitlab.get("base_url"),
            default="https://gitlab.com",
        ).rstrip("/"),
    )
    clone_protocol = _read_text(defaults.get("clone_protocol"), default="https").lower()
    if clone_protocol not in {"https", "ssh"}:
        raise RemoteCatalogError("tui.defaults.clone_protocol must be 'https' or 'ssh'.")

    if not github_settings.enabled and not gitlab_settings.enabled:
        raise RemoteCatalogError("At least one TUI provider must be enabled.")

    return TuiSettings(
        providers=TuiProviderSettings(github=github_settings, gitlab=gitlab_settings),
        defaults=TuiDefaults(clone_protocol=clone_protocol),
    )


def _request_json(url: str, headers: dict[str, str]) -> Any:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "analyze-git-repo-loc",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_github_repositories(
    *,
    api_base_url: str,
    token: str,
) -> list[RemoteRepositoryRef]:
    """
    Fetch repositories accessible to the authenticated GitHub user.

    Args:
        api_base_url (str): GitHub API base URL.
        token (str): GitHub token from `GITHUB_TOKEN`.

    Returns:
        list[RemoteRepositoryRef]: Normalized repository refs.
    """
    refs: list[RemoteRepositoryRef] = []
    page = 1
    while True:
        query = urlencode(
            {
                "per_page": 100,
                "page": page,
                "affiliation": "owner,collaborator,organization_member",
                "sort": "full_name",
            }
        )
        url = f"{api_base_url.rstrip('/')}/user/repos?{query}"
        payload = _request_json(url, _github_headers(token))
        if not isinstance(payload, list):
            raise RemoteCatalogError("GitHub API response must be a list.")
        for item in payload:
            if not isinstance(item, dict):
                continue
            clone_url = item.get("clone_url") or ""
            full_name = item.get("full_name") or item.get("name") or ""
            if not clone_url or not full_name:
                continue
            refs.append(
                RemoteRepositoryRef(
                    provider="github",
                    name=item.get("name") or full_name.rsplit("/", 1)[-1],
                    full_name=full_name,
                    clone_url=clone_url,
                    ssh_url=item.get("ssh_url") or "",
                    web_url=item.get("html_url") or "",
                    default_branch=item.get("default_branch") or "main",
                )
            )
        if len(payload) < 100:
            break
        page += 1
    return refs


def _gitlab_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "PRIVATE-TOKEN": token,
        "User-Agent": "analyze-git-repo-loc",
    }


def fetch_gitlab_repositories(
    *,
    base_url: str,
    token: str,
) -> list[RemoteRepositoryRef]:
    """
    Fetch projects accessible to the authenticated GitLab user.

    Args:
        base_url (str): GitLab instance base URL.
        token (str): GitLab token from `GITLAB_TOKEN`.

    Returns:
        list[RemoteRepositoryRef]: Normalized repository refs.
    """
    refs: list[RemoteRepositoryRef] = []
    page = 1
    while True:
        query = urlencode(
            {
                "membership": "true",
                "simple": "true",
                "per_page": 100,
                "page": page,
                "order_by": "path",
                "sort": "asc",
            }
        )
        url = urljoin(f"{base_url.rstrip('/')}/", f"api/v4/projects?{query}")
        payload = _request_json(url, _gitlab_headers(token))
        if not isinstance(payload, list):
            raise RemoteCatalogError("GitLab API response must be a list.")
        for item in payload:
            if not isinstance(item, dict):
                continue
            clone_url = item.get("http_url_to_repo") or ""
            full_name = item.get("path_with_namespace") or item.get("name") or ""
            if not clone_url or not full_name:
                continue
            refs.append(
                RemoteRepositoryRef(
                    provider="gitlab",
                    name=item.get("name") or full_name.rsplit("/", 1)[-1],
                    full_name=full_name,
                    clone_url=clone_url,
                    ssh_url=item.get("ssh_url_to_repo") or "",
                    web_url=item.get("web_url") or "",
                    default_branch=item.get("default_branch") or "main",
                )
            )
        if len(payload) < 100:
            break
        page += 1
    return refs


def fetch_remote_repositories(settings: TuiSettings) -> list[RemoteRepositoryRef]:
    """
    Fetch repositories from all enabled TUI providers.

    Args:
        settings (TuiSettings): Validated TUI settings.

    Returns:
        list[RemoteRepositoryRef]: Sorted repository refs.

    Raises:
        RemoteCatalogError: If tokens are missing, APIs fail, or no repos exist.
    """
    refs: list[RemoteRepositoryRef] = []
    try:
        if settings.providers.github.enabled:
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                raise RemoteCatalogError(
                    "GITHUB_TOKEN is required when GitHub TUI provider is enabled."
                )
            refs.extend(
                fetch_github_repositories(
                    api_base_url=settings.providers.github.api_base_url,
                    token=token,
                )
            )
        if settings.providers.gitlab.enabled:
            token = os.getenv("GITLAB_TOKEN")
            if not token:
                raise RemoteCatalogError(
                    "GITLAB_TOKEN is required when GitLab TUI provider is enabled."
                )
            refs.extend(
                fetch_gitlab_repositories(
                    base_url=settings.providers.gitlab.base_url,
                    token=token,
                )
            )
    except RemoteCatalogError:
        raise
    except OSError as ex:
        raise RemoteCatalogError(f"Failed to fetch remote repositories: {ex}") from ex
    except json.JSONDecodeError as ex:
        raise RemoteCatalogError("Provider API response was not valid JSON.") from ex

    if not refs:
        raise RemoteCatalogError("No repositories were returned by enabled providers.")
    return sorted(refs, key=lambda ref: (ref.provider, ref.full_name.lower()))


def selected_refs_to_repo_paths(
    selected_refs: list[RemoteRepositoryRef],
    *,
    clone_protocol: str,
) -> list[tuple[str, str, list[str]]]:
    """
    Convert selected repository refs to the existing `args.repo_paths` shape.

    Args:
        selected_refs (list[RemoteRepositoryRef]): Selected repositories.
        clone_protocol (str): `https` or `ssh`.

    Returns:
        list[tuple[str, str, list[str]]]: Existing repository tuple format.
    """
    return [
        (ref.git_url(clone_protocol), ref.default_branch or "main", [])
        for ref in selected_refs
    ]
