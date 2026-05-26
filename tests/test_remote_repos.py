"""Tests for remote repository cache handling."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from analyze_git_repo_loc.remote_auth import RemoteAuthService
from analyze_git_repo_loc.remote_auth import build_host_token_env_var
from analyze_git_repo_loc.remote_repos import RemoteRepoManager


class RemoteRepoManagerCacheTests(unittest.TestCase):
    """Remote repository cache path and cleanup tests."""

    def test_cache_path_uses_remote_identity_to_avoid_name_collisions(self) -> None:
        manager = RemoteRepoManager()
        cache_dir = Path("out") / ".cache"

        first = manager._get_remote_cache_path(
            cache_dir,
            "https://github.com/acme/AnalyzeGitRepoLoc.git",
        )
        second = manager._get_remote_cache_path(
            cache_dir,
            "https://github.com/other/AnalyzeGitRepoLoc.git",
        )

        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, cache_dir / "remote-repos")
        self.assertTrue(first.name.startswith("AnalyzeGitRepoLoc-"))

    def test_remove_cache_path_retries_readonly_files_as_writable(self) -> None:
        manager = RemoteRepoManager()
        failed_path = "repo/.git/objects/pack/file.idx"
        retry = Mock()

        with patch("os.chmod") as chmod:
            manager._handle_remove_error(retry, failed_path, PermissionError("denied"))

        chmod.assert_called_once_with(failed_path, 0o700)
        retry.assert_called_once_with(failed_path)

    def test_remove_cache_path_calls_rmtree_with_error_handler(self) -> None:
        manager = RemoteRepoManager()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "repo"
            path.mkdir()

            with patch("shutil.rmtree") as rmtree:
                manager._remove_cache_path(path)

        rmtree.assert_called_once_with(path, onexc=manager._handle_remove_error)

    def test_clone_uses_noninteractive_git_auth_env(self) -> None:
        auth = Mock()
        auth.build_auth_candidates.return_value = ["https://github.com/acme/private.git"]
        auth.git_env.return_value = {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
        }
        auth.strip_credentials.side_effect = lambda value: value
        manager = RemoteRepoManager(auth)
        repo = Mock()

        with patch("analyze_git_repo_loc.remote_repos.Repo.clone_from", return_value=repo) as clone:
            result = manager._clone_with_auth(
                "https://github.com/acme/private.git",
                Path("cache/private"),
            )

        self.assertIs(result, repo)
        clone.assert_called_once_with(
            "https://github.com/acme/private.git",
            Path("cache/private"),
            env={
                "GIT_TERMINAL_PROMPT": "0",
                "GCM_INTERACTIVE": "never",
            },
        )

    def test_fetch_uses_noninteractive_git_auth_env(self) -> None:
        auth = Mock()
        auth.build_auth_candidates.return_value = ["https://github.com/acme/private.git"]
        auth.git_env.return_value = {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
        }
        manager = RemoteRepoManager(auth)
        repo = Mock()
        origin = repo.remotes.origin
        origin.url = "https://github.com/acme/private.git"

        manager._fetch_with_auth(repo, "https://github.com/acme/private.git")

        repo.git.fetch.assert_called_once_with(
            "--all",
            "--prune",
            env={
                "GIT_TERMINAL_PROMPT": "0",
                "GCM_INTERACTIVE": "never",
            },
        )


class RemoteAuthServiceTests(unittest.TestCase):
    """Remote authentication token resolution tests."""

    def test_host_specific_token_is_used_for_self_hosted_gitlab(self) -> None:
        auth = RemoteAuthService()
        env_name = build_host_token_env_var("git.example.com")

        with patch.dict("os.environ", {env_name: "host-token"}, clear=True):
            candidates = auth.build_auth_candidates(
                "https://git.example.com/team/private.git"
            )

        self.assertEqual(
            candidates[0],
            "https://oauth2:host-token@git.example.com/team/private.git",
        )

    def test_github_cli_token_is_used_when_env_token_is_missing(self) -> None:
        auth = RemoteAuthService()
        runner = Mock(return_value=Mock(returncode=0, stdout="gh-token\n"))

        with patch.dict("os.environ", {}, clear=True):
            with patch("analyze_git_repo_loc.remote_auth.shutil.which", return_value="gh"):
                with patch("analyze_git_repo_loc.remote_auth.subprocess.run", runner):
                    candidates = auth.build_auth_candidates(
                        "https://github.com/acme/private.git"
                    )

        self.assertEqual(
            candidates[0],
            "https://x-access-token:gh-token@github.com/acme/private.git",
        )
        runner.assert_called_once_with(
            ["gh", "auth", "token", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_gitlab_cli_token_is_used_when_env_token_is_missing(self) -> None:
        auth = RemoteAuthService()
        runner = Mock(
            return_value=Mock(
                returncode=0,
                stdout="gitlab.com\n  Token: glpat-token\n",
            )
        )

        with patch.dict("os.environ", {}, clear=True):
            with patch("analyze_git_repo_loc.remote_auth.shutil.which", return_value="glab"):
                with patch("analyze_git_repo_loc.remote_auth.subprocess.run", runner):
                    candidates = auth.build_auth_candidates(
                        "https://gitlab.com/acme/private.git"
                    )

        self.assertEqual(
            candidates[0],
            "https://oauth2:glpat-token@gitlab.com/acme/private.git",
        )

    def test_git_commands_disable_interactive_credential_prompts(self) -> None:
        auth = RemoteAuthService()

        self.assertEqual(
            auth.git_env(),
            {
                "GIT_TERMINAL_PROMPT": "0",
                "GCM_INTERACTIVE": "never",
            },
        )


if __name__ == "__main__":
    unittest.main()
