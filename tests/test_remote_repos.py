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


if __name__ == "__main__":
    unittest.main()
