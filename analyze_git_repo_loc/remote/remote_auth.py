"""
Remote authentication helpers for Git repositories.

Classes:
    RemoteAuthError: Raised when authentication fails.
    RemoteAuthService: Builds auth candidates and interprets auth results.

Public methods:
    RemoteAuthService.build_auth_candidates
    RemoteAuthService.strip_credentials
    RemoteAuthService.log_auth_success
    RemoteAuthService.is_auth_failure
    RemoteAuthService.raise_auth_failure
Functions:
    build_host_token_env_var:
        Build the process-local environment variable name for a host token.

Overview:
    Encapsulates token resolution, HTTPS token URL construction, credential
    stripping, auth-success logging, and auth-failure detection/raising.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable
from urllib.parse import ParseResult, urlparse

from git import GitCommandError
from tqdm import tqdm


class RemoteAuthError(ValueError):
    """Authentication failed while accessing a remote repository."""


def build_host_token_env_var(host: str) -> str:
    """
    Build the environment variable name used for a host-specific token.

    Args:
        host (str): Git hosting hostname.

    Returns:
        str: Process environment variable name for the host token.
    """
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", host).strip("_").upper()
    return f"ANALYZE_GIT_REPO_LOC_TOKEN_{normalized}"


def build_host_provider_env_var(host: str) -> str:
    """
    Build the environment variable name used for a host-specific provider hint.

    Args:
        host (str): Git hosting hostname.

    Returns:
        str: Process environment variable name for the host provider hint.
    """
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", host).strip("_").upper()
    return f"ANALYZE_GIT_REPO_LOC_PROVIDER_{normalized}"


def get_cli_token(
    provider: str,
    base_url: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> str | None:
    """
    Return a token from `gh` or `glab` when a CLI login is available.

    Args:
        provider (str): `github` or `gitlab`.
        base_url (str): Provider API or instance base URL.
        runner (Callable | None): Command runner, injected by tests.

    Returns:
        str | None: CLI token, or None if unavailable.
    """
    hostname = _hostname_from_base_url(provider, base_url)
    if provider == "github":
        command = ["gh", "auth", "token", "--hostname", hostname]
    elif provider == "gitlab":
        command = [
            "glab",
            "auth",
            "status",
            "--hostname",
            hostname,
            "--show-token",
        ]
    else:
        return None
    if shutil.which(command[0]) is None:
        return None

    command_runner = runner or subprocess.run
    try:
        result = command_runner(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    if provider == "github":
        return output or None
    return _parse_glab_token(output)


def _hostname_from_base_url(provider: str, base_url: str) -> str:
    if provider == "github" and base_url.rstrip("/") == "https://api.github.com":
        return "github.com"
    parsed = urlparse(base_url)
    return (
        parsed.hostname
        or base_url.replace("https://", "").replace("http://", "").split("/")[0]
    )


def _parse_glab_token(output: str) -> str | None:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("token:"):
            token = stripped.split(":", 1)[1].strip()
            return token or None
    return None


def _provider_from_hostname(hostname: str) -> str | None:
    normalized = hostname.lower()
    if "github" in normalized:
        return "github"
    if "gitlab" in normalized:
        return "gitlab"
    return None


def _normalize_provider_name(provider: str | None) -> str | None:
    normalized = (provider or "").strip().lower()
    if normalized in {"github", "gitlab"}:
        return normalized
    return None


def _provider_hint_for_hostname(hostname: str) -> str | None:
    return _normalize_provider_name(
        os.getenv(build_host_provider_env_var(hostname.lower()))
    )


def _base_url_for_hostname(parsed_url: ParseResult) -> str:
    netloc = parsed_url.hostname or ""
    if parsed_url.port:
        netloc = f"{netloc}:{parsed_url.port}"
    return parsed_url._replace(
        netloc=netloc,
        path="",
        params="",
        query="",
        fragment="",
    ).geturl()


class RemoteAuthService:
    """Encapsulates remote authentication helpers."""

    _AUTH_LOG_ENV = "ANALYZE_GIT_REPO_LOC_LOG_AUTH"
    _NONINTERACTIVE_GIT_ENV = {
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "never",
    }

    def build_auth_candidates(self, repo_url: str) -> list[str]:
        """
        Build ordered clone/fetch URLs based on the provided scheme.

        Args:
            repo_url (str): Repository URL.

        Returns:
            list[str]: Ordered list of URLs to try.
        """
        parsed = urlparse(repo_url)
        candidates: list[str] = []
        if repo_url.startswith("git@") or parsed.scheme in {"ssh", "git"}:
            candidates.append(repo_url)
        elif parsed.scheme in {"http", "https"}:
            token_url = self._build_https_token_url(repo_url)
            if token_url:
                candidates.append(token_url)
            cli_token_url = self._build_https_cli_token_url(repo_url)
            if cli_token_url:
                candidates.append(cli_token_url)
            candidates.append(repo_url)
        else:
            candidates.append(repo_url)

        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate not in seen:
                unique.append(candidate)
                seen.add(candidate)
        return unique

    def git_env(self) -> dict[str, str]:
        """
        Return Git environment overrides for non-interactive command execution.

        Returns:
            dict[str, str]: Environment variables that disable credential prompts.
        """
        return dict(self._NONINTERACTIVE_GIT_ENV)

    def strip_credentials(self, repo_url: str) -> str:
        """
        Remove embedded credentials from an HTTPS URL.

        Args:
            repo_url (str): Repository URL.

        Returns:
            str: Sanitized URL without user info.
        """
        parsed = urlparse(repo_url)
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            netloc = parsed.hostname
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            return parsed._replace(netloc=netloc).geturl()
        return repo_url

    def log_auth_success(self, candidate: str) -> None:
        """
        Log the authentication method used to access a remote repository.

        Args:
            candidate (str): Clone/fetch URL that succeeded.
        """
        if not self._is_auth_log_enabled():
            return
        sanitized = self.strip_credentials(candidate)
        method = self._describe_auth_method(candidate)
        tqdm.write(f"Authentication succeeded: {method} ({sanitized})")

    @classmethod
    def _is_auth_log_enabled(cls) -> bool:
        """
        Determine whether authentication logs should be emitted.
        """
        return os.getenv(cls._AUTH_LOG_ENV, "1") != "0"

    def is_auth_failure(self, error: GitCommandError) -> bool:
        """
        Check whether a Git error looks like an authentication failure.

        Args:
            error (GitCommandError): Git error to inspect.

        Returns:
            bool: True when the error indicates authentication failure.
        """
        stderr = (error.stderr or "").lower()
        return any(
            phrase in stderr
            for phrase in (
                "authentication failed",
                "invalid username or token",
                "password authentication is not supported",
                "could not read username",
                "permission denied (publickey)",
            )
        )

    def raise_auth_failure(self, repo_url: str, error: GitCommandError) -> None:
        """
        Raise a friendly authentication error for a remote repository.

        Args:
            repo_url (str): Repository URL.
            error (GitCommandError): Underlying Git error.
        """
        parsed = urlparse(repo_url)
        if repo_url.startswith("git@") or parsed.scheme in {"ssh", "git"}:
            hint = "Ensure your SSH keys have access to the repository."
        elif parsed.scheme in {"http", "https"}:
            hint = (
                "For private repositories, set GITHUB_TOKEN or GITLAB_TOKEN, "
                "or use an SSH URL."
            )
        else:
            hint = "Provide valid credentials for the repository URL and retry."
        message = f"Authentication failed for '{repo_url}'. {hint}"
        raise RemoteAuthError(message) from error

    def _get_token_for_host(self, host: str | None) -> tuple[str, str] | None:
        """
        Resolve a Git hosting token and username based on the host name.

        Args:
            host (str | None): Host name from the repository URL.

        Returns:
            tuple[str, str] | None: (token, username) pair when configured.
        """
        if not host:
            return None
        normalized = host.lower()
        provider = self._provider_for_host(normalized)
        host_token = os.getenv(build_host_token_env_var(normalized))
        if host_token:
            return host_token, self._username_for_provider(provider)
        return self._provider_token(provider)

    def _provider_for_host(self, normalized_host: str) -> str | None:
        """Infer the hosting provider for a normalized host name."""
        provider = _provider_hint_for_hostname(normalized_host)
        if provider is not None:
            return provider
        provider = _provider_from_hostname(normalized_host)
        if provider is not None:
            return provider
        return self._sole_configured_provider()

    def _sole_configured_provider(self) -> str | None:
        """Return the only configured provider when exactly one token exists."""
        github_token = os.getenv("GITHUB_TOKEN")
        gitlab_token = os.getenv("GITLAB_TOKEN")
        if github_token and not gitlab_token:
            return "github"
        if gitlab_token and not github_token:
            return "gitlab"
        return None

    def _provider_token(self, provider: str | None) -> tuple[str, str] | None:
        """Return the configured token pair for the selected provider."""
        if provider == "github":
            token = os.getenv("GITHUB_TOKEN")
            if token:
                return token, "x-access-token"
        if provider == "gitlab":
            token = os.getenv("GITLAB_TOKEN")
            if token:
                return token, "oauth2"
        return None

    def _username_for_provider(self, provider: str | None) -> str:
        """Return the HTTPS username used for token-authenticated Git URLs."""
        if provider == "github":
            return "x-access-token"
        return "oauth2"

    def _build_https_token_url(self, repo_url: str) -> str | None:
        """
        Build an HTTPS URL embedding a token for authentication.

        Args:
            repo_url (str): Repository URL.

        Returns:
            str | None: Token-authenticated URL when a token is available.
        """
        parsed = urlparse(repo_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        token_info = self._get_token_for_host(parsed.hostname)
        if token_info is None:
            return None
        token, username = token_info
        return self._build_https_url_with_token(repo_url, token, username)

    def _build_https_cli_token_url(self, repo_url: str) -> str | None:
        """
        Build an HTTPS URL using a token from GitHub/GitLab CLI login.

        Args:
            repo_url (str): Repository URL.

        Returns:
            str | None: Token-authenticated URL when CLI auth is available.
        """
        parsed = urlparse(repo_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        provider = _provider_hint_for_hostname(
            parsed.hostname
        ) or _provider_from_hostname(parsed.hostname)
        if provider is None:
            return None
        token = get_cli_token(provider, _base_url_for_hostname(parsed))
        if not token:
            return None
        username = "x-access-token" if provider == "github" else "oauth2"
        return self._build_https_url_with_token(repo_url, token, username)

    def _build_https_url_with_token(
        self,
        repo_url: str,
        token: str,
        username: str,
    ) -> str | None:
        """
        Build an HTTPS URL embedding a username/token pair.

        Args:
            repo_url (str): Repository URL.
            token (str): Access token.
            username (str): Token username for the Git hosting provider.

        Returns:
            str | None: Token-authenticated URL.
        """
        parsed = urlparse(repo_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        netloc = f"{username}:{token}@{parsed.hostname}"
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return parsed._replace(netloc=netloc).geturl()

    def _describe_auth_method(self, candidate: str) -> str:
        """
        Describe the authentication method implied by a clone/fetch URL.

        Args:
            candidate (str): Clone/fetch URL used for authentication.

        Returns:
            str: Human-readable authentication method label.
        """
        if candidate.startswith("git@"):
            return "SSH"
        parsed = urlparse(candidate)
        if parsed.scheme in {"ssh", "git"}:
            return "SSH"
        if parsed.scheme in {"http", "https"}:
            return "HTTPS"
        return "Unknown"
