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

Overview:
    Encapsulates token resolution, HTTPS token URL construction, credential
    stripping, auth-success logging, and auth-failure detection/raising.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from git import GitCommandError
from tqdm import tqdm


class RemoteAuthError(ValueError):
    """Authentication failed while accessing a remote repository."""


class RemoteAuthService:
    """Encapsulates remote authentication helpers."""

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
        sanitized = self.strip_credentials(candidate)
        method = self._describe_auth_method(candidate)
        tqdm.write(f"Authentication succeeded: {method} ({sanitized})")

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
        if "github" in normalized:
            token = os.getenv("GITHUB_TOKEN")
            if token:
                return token, "x-access-token"
        if "gitlab" in normalized:
            token = os.getenv("GITLAB_TOKEN")
            if token:
                return token, "oauth2"
        return None

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
