"""
Remote repository helpers for cloning, fetching, and caching.

Classes:
    RemoteRepoManager: Manages remote URL detection and clone/update workflow.

Public methods:
    RemoteRepoManager.is_git_url
    RemoteRepoManager.prepare_remote_repository

Overview:
    Provides cached clone path resolution, origin validation, fetch/clone
    handling, and branch checkout using RemoteAuthService for authentication.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import urlparse

from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo

from analyze_git_repo_loc.git_repo_loc_analyzer import GitRepoLOCAnalyzer
from analyze_git_repo_loc.remote_auth import RemoteAuthService


class RemoteRepoManager:
    """Encapsulates remote repository clone/update logic."""

    def __init__(self, auth_service: RemoteAuthService | None = None) -> None:
        self._auth = auth_service or RemoteAuthService()

    def is_git_url(self, value: str) -> bool:
        """
        Detect whether a string is a git URL.

        Args:
            value (str): The input string to inspect.

        Returns:
            bool: True if the input looks like a git URL.
        """
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https", "ssh", "git"}:
            return True
        return value.startswith("git@") and ":" in value

    def prepare_remote_repository(
        self, repo_url: str, branch_name: str, cache_dir: Path
    ) -> Path:
        """
        Clone or update a remote repository in the local cache.

        Args:
            repo_url (str): Remote repository URL.
            branch_name (str): Branch to check out.
            cache_dir (Path): Base cache directory for clones.

        Returns:
            Path: Local path to the cached clone.
        """
        repo_path = self._get_remote_cache_path(cache_dir, repo_url)
        try:
            repo = Repo(repo_path)
            self._ensure_origin_matches(repo, repo_url)
            self._fetch_with_auth(repo, repo_url)
        except (InvalidGitRepositoryError, NoSuchPathError):
            if repo_path.exists():
                shutil.rmtree(repo_path)
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                repo = self._clone_with_auth(repo_url, repo_path)
            except GitCommandError as ex:
                raise ValueError(f"Failed to clone remote repository: {ex}") from ex
        except GitCommandError as ex:
            raise ValueError(f"Failed to update remote repository: {ex}") from ex
        self._checkout_branch(repo, branch_name)
        return repo_path

    def _parse_repo_identity(self, repo_url: str) -> tuple[str, str] | None:
        """
        Normalize a repository URL into a comparable (host, path) identity.

        Args:
            repo_url (str): Repository URL to normalize.

        Returns:
            tuple[str, str] | None: Normalized identity for comparison.
        """
        if repo_url.startswith("git@"):
            host_path = repo_url.split("@", 1)[-1]
            if ":" not in host_path:
                return None
            host, path = host_path.split(":", 1)
            return host.lower(), path.lstrip("/")
        parsed = urlparse(repo_url)
        if parsed.hostname and parsed.path:
            return parsed.hostname.lower(), parsed.path.lstrip("/")
        return None

    def _ensure_origin_matches(self, repo: Repo, repo_url: str) -> None:
        """
        Validate that the cached repository origin matches the requested repository.

        Args:
            repo (Repo): Cached repository.
            repo_url (str): Requested repository URL.

        Raises:
            ValueError: If the cached repository points to a different origin.
        """
        origin_url = repo.remotes.origin.url if repo.remotes else None
        if origin_url is None:
            return
        origin_identity = self._parse_repo_identity(origin_url)
        requested_identity = self._parse_repo_identity(repo_url)
        if origin_identity and requested_identity and origin_identity != requested_identity:
            raise ValueError(
                f"Cached repository at {repo.working_tree_dir} does not match {repo_url}."
            )

    def _fetch_with_auth(self, repo: Repo, repo_url: str) -> None:
        """
        Fetch updates using SSH first, with HTTPS token fallback when configured.

        Args:
            repo (Repo): Cached repository.
            repo_url (str): Requested repository URL.
        """
        origin = repo.remotes.origin if repo.remotes else None
        if origin is None:
            origin = repo.create_remote("origin", self._auth.strip_credentials(repo_url))
        original_url = origin.url
        last_error: GitCommandError | None = None
        for candidate in self._auth.build_auth_candidates(repo_url):
            try:
                if origin.url != candidate:
                    origin.set_url(candidate)
                repo.git.fetch("--all", "--prune")
                self._auth.log_auth_success(repo_url, candidate)
                return
            except GitCommandError as ex:
                last_error = ex
            finally:
                if origin.url != original_url:
                    origin.set_url(original_url)
        if last_error is not None:
            if self._auth.is_auth_failure(last_error):
                self._auth.raise_auth_failure(repo_url, last_error)
            raise last_error

    def _clone_with_auth(self, repo_url: str, repo_path: Path) -> Repo:
        """
        Clone a repository using SSH first and HTTPS token fallback.

        Args:
            repo_url (str): Requested repository URL.
            repo_path (Path): Local clone path.

        Returns:
            Repo: Cloned repository.
        """
        last_error: GitCommandError | None = None
        for candidate in self._auth.build_auth_candidates(repo_url):
            try:
                repo = Repo.clone_from(candidate, repo_path)
                sanitized_candidate = self._auth.strip_credentials(candidate)
                if repo.remotes and repo.remotes.origin.url != sanitized_candidate:
                    repo.remotes.origin.set_url(sanitized_candidate)
                self._auth.log_auth_success(repo_url, candidate)
                return repo
            except GitCommandError as ex:
                last_error = ex
                if repo_path.exists():
                    shutil.rmtree(repo_path)
        if last_error is not None:
            if self._auth.is_auth_failure(last_error):
                self._auth.raise_auth_failure(repo_url, last_error)
            raise last_error
        raise ValueError("No authentication candidates available for clone.")

    def _get_remote_cache_path(self, cache_dir: Path, repo_url: str) -> Path:
        """
        Build a cache directory path for a remote repository clone.

        Args:
            cache_dir (Path): Base cache directory.
            repo_url (str): Remote repository URL.

        Returns:
            Path: Path to the cached clone.
        """
        repo_name = GitRepoLOCAnalyzer.get_repository_name(repo_url)
        return cache_dir / "remote-repos" / repo_name

    def _checkout_branch(self, repo: Repo, branch_name: str) -> None:
        """
        Ensure the target branch is checked out.

        Args:
            repo (Repo): GitPython repository instance.
            branch_name (str): Branch to check out.

        Raises:
            ValueError: If the branch does not exist.
        """
        if branch_name in repo.heads:
            repo.git.checkout(branch_name)
            return
        remote_ref = f"origin/{branch_name}"
        remote_refs = [ref.name for ref in repo.remotes.origin.refs]
        if remote_ref in remote_refs:
            repo.git.checkout("-B", branch_name, remote_ref)
            return
        raise ValueError(f"Branch '{branch_name}' not found in remote repository.")
