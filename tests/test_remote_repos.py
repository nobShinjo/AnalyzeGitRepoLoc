"""Tests for remote repository cache handling."""

from __future__ import annotations

# pylint: disable=missing-function-docstring

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from analyze_git_repo_loc.remote.remote_auth import build_host_provider_env_var
from analyze_git_repo_loc.remote.remote_auth import RemoteAuthService
from analyze_git_repo_loc.remote.remote_auth import build_host_token_env_var
from analyze_git_repo_loc.remote.remote_repos import RemoteRepoManager

GITHUB_ANALYZER_URL = "https://github.com/acme/AnalyzeGitRepoLoc.git"
GITHUB_ANALYZER_URL_NO_DOT_GIT = "https://github.com/acme/AnalyzeGitRepoLoc"
GITHUB_PRIVATE_REPO_URL = "https://github.com/acme/private.git"
SELF_HOSTED_GITHUB_PRIVATE_REPO_URL = "https://git.example.com/team/private.git"
SELF_HOSTED_GITHUB_ACME_REPO_URL = "https://git.example.com/acme/private.git"
GITLAB_PRIVATE_REPO_URL = "https://gitlab.com/acme/private.git"


def _https_auth_url(username: str, token: str, host: str, path: str) -> str:
    return f"https://{username}:{token}@{host}/{path}"


class RemoteRepoManagerCacheTests(unittest.TestCase):
    """Remote repository cache path and cleanup tests."""

    def test_origin_match_treats_dot_git_suffix_as_equivalent(self) -> None:
        manager = RemoteRepoManager()
        repo = Mock()
        repo.remotes = Mock()
        repo.remotes.origin.url = GITHUB_ANALYZER_URL
        repo.working_tree_dir = "cache/repo"

        # pylint: disable-next=protected-access
        manager._ensure_origin_matches(
            repo,
            GITHUB_ANALYZER_URL_NO_DOT_GIT,
        )

    def test_cache_path_uses_remote_identity_to_avoid_name_collisions(self) -> None:
        manager = RemoteRepoManager()
        cache_dir = Path("out") / ".cache"

        first = manager.get_remote_cache_path(
            cache_dir,
            GITHUB_ANALYZER_URL,
        )
        second = manager.get_remote_cache_path(
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
            # pylint: disable-next=protected-access
            manager._handle_remove_error(retry, failed_path, PermissionError("denied"))

        chmod.assert_called_once_with(failed_path, 0o700)
        retry.assert_called_once_with(failed_path)

    def test_remove_cache_path_calls_rmtree_with_error_handler(self) -> None:
        manager = RemoteRepoManager()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "repo"
            path.mkdir()

            with patch("shutil.rmtree") as rmtree:
                # pylint: disable-next=protected-access
                manager._remove_cache_path(path)

        rmtree.assert_called_once()
        self.assertEqual(rmtree.call_args.args, (path,))
        onexc = rmtree.call_args.kwargs["onexc"]
        self.assertIs(getattr(onexc, "__self__", None), manager)
        self.assertEqual(getattr(onexc, "__name__", ""), "_handle_remove_error")

    def test_clone_uses_noninteractive_git_auth_env(self) -> None:
        auth = Mock()
        auth.build_auth_candidates.return_value = [GITHUB_PRIVATE_REPO_URL]
        auth.git_env.return_value = {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
        }
        auth.strip_credentials.side_effect = lambda value: value
        manager = RemoteRepoManager(auth)
        repo = Mock()

        with patch(
            "analyze_git_repo_loc.remote.remote_repos.Repo.clone_from",
            return_value=repo,
        ) as clone:
            # pylint: disable-next=protected-access
            result = manager._clone_with_auth(
                GITHUB_PRIVATE_REPO_URL,
                Path("cache/private"),
            )

        self.assertIs(result, repo)
        clone.assert_called_once_with(
            GITHUB_PRIVATE_REPO_URL,
            Path("cache/private"),
            env={
                "GIT_TERMINAL_PROMPT": "0",
                "GCM_INTERACTIVE": "never",
            },
        )

    def test_fetch_uses_noninteractive_git_auth_env(self) -> None:
        auth = Mock()
        auth.build_auth_candidates.return_value = [GITHUB_PRIVATE_REPO_URL]
        auth.git_env.return_value = {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
        }
        manager = RemoteRepoManager(auth)
        repo = Mock()
        origin = repo.remotes.origin
        origin.url = GITHUB_PRIVATE_REPO_URL

        # pylint: disable-next=protected-access
        manager._fetch_with_auth(repo, GITHUB_PRIVATE_REPO_URL)

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
                SELF_HOSTED_GITHUB_PRIVATE_REPO_URL
            )

        self.assertEqual(
            candidates[0],
            _https_auth_url(
                "oauth2",
                "host-token",
                "git.example.com",
                "team/private.git",
            ),
        )

    def test_host_specific_token_uses_github_username_with_provider_hint(self) -> None:
        auth = RemoteAuthService()
        env_name = build_host_token_env_var("git.example.com")
        provider_env = build_host_provider_env_var("git.example.com")

        with patch.dict(
            "os.environ",
            {env_name: "host-token", provider_env: "github"},
            clear=True,
        ):
            candidates = auth.build_auth_candidates(
                SELF_HOSTED_GITHUB_PRIVATE_REPO_URL
            )

        self.assertEqual(
            candidates[0],
            _https_auth_url(
                "x-access-token",
                "host-token",
                "git.example.com",
                "team/private.git",
            ),
        )

    def test_github_token_fallback_uses_provider_hint_for_self_hosted_github(self) -> None:
        auth = RemoteAuthService()
        provider_env = build_host_provider_env_var("git.example.com")

        with patch.dict(
            "os.environ",
            {provider_env: "github", "GITHUB_TOKEN": "gh-token"},
            clear=True,
        ):
            candidates = auth.build_auth_candidates(
                SELF_HOSTED_GITHUB_PRIVATE_REPO_URL
            )

        self.assertEqual(
            candidates[0],
            _https_auth_url(
                "x-access-token",
                "gh-token",
                "git.example.com",
                "team/private.git",
            ),
        )

    def test_github_cli_token_uses_provider_hint_for_self_hosted_github(self) -> None:
        auth = RemoteAuthService()
        provider_env = build_host_provider_env_var("git.example.com")
        runner = Mock(return_value=Mock(returncode=0, stdout="gh-token\n"))

        with patch.dict("os.environ", {provider_env: "github"}, clear=True):
            with patch(
                "analyze_git_repo_loc.remote.remote_auth.shutil.which",
                return_value="gh",
            ):
                with patch(
                    "analyze_git_repo_loc.remote.remote_auth.subprocess.run",
                    runner,
                ):
                    candidates = auth.build_auth_candidates(
                        SELF_HOSTED_GITHUB_ACME_REPO_URL
                    )

        self.assertEqual(
            candidates[0],
            _https_auth_url(
                "x-access-token",
                "gh-token",
                "git.example.com",
                "acme/private.git",
            ),
        )
        runner.assert_called_once_with(
            ["gh", "auth", "token", "--hostname", "git.example.com"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    def test_github_cli_token_is_used_when_env_token_is_missing(self) -> None:
        auth = RemoteAuthService()
        runner = Mock(return_value=Mock(returncode=0, stdout="gh-token\n"))

        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "analyze_git_repo_loc.remote.remote_auth.shutil.which",
                return_value="gh",
            ):
                with patch(
                    "analyze_git_repo_loc.remote.remote_auth.subprocess.run",
                    runner,
                ):
                    candidates = auth.build_auth_candidates(
                        GITHUB_PRIVATE_REPO_URL
                    )

        self.assertEqual(
            candidates[0],
            _https_auth_url(
                "x-access-token",
                "gh-token",
                "github.com",
                "acme/private.git",
            ),
        )
        runner.assert_called_once_with(
            ["gh", "auth", "token", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
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
            with patch(
                "analyze_git_repo_loc.remote.remote_auth.shutil.which",
                return_value="glab",
            ):
                with patch(
                    "analyze_git_repo_loc.remote.remote_auth.subprocess.run",
                    runner,
                ):
                    candidates = auth.build_auth_candidates(
                        GITLAB_PRIVATE_REPO_URL
                    )

        self.assertEqual(
            candidates[0],
            _https_auth_url(
                "oauth2",
                "glpat-token",
                "gitlab.com",
                "acme/private.git",
            ),
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
