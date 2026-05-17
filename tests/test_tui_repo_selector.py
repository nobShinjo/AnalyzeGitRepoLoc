"""Tests for the GitHub/GitLab repository selector TUI."""

from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analyze_git_repo_loc import remote_catalog
from analyze_git_repo_loc.__main__ import _apply_tui_repository_selection
from analyze_git_repo_loc.remote_catalog import (
    RemoteCatalogError,
    RemoteRepositoryRef,
    fetch_github_repositories,
    fetch_gitlab_repositories,
    fetch_remote_repositories,
    load_tui_settings,
    selected_refs_to_repo_paths,
)
from analyze_git_repo_loc.tui_selector import (
    RepositorySelectorState,
    TuiSelectionCancelled,
)
from analyze_git_repo_loc.utils import parse_arguments


class TuiConfigTests(unittest.TestCase):
    """TUI config loading tests."""

    def test_loads_tui_settings_with_defaults(self) -> None:
        config = {
            "tui": {
                "providers": {
                    "github": {"enabled": True},
                    "gitlab": {"enabled": True, "base_url": "https://git.example"},
                }
            }
        }

        settings = load_tui_settings(config)

        self.assertTrue(settings.providers.github.enabled)
        self.assertEqual(settings.providers.github.api_base_url, "https://api.github.com")
        self.assertTrue(settings.providers.gitlab.enabled)
        self.assertEqual(settings.providers.gitlab.base_url, "https://git.example")
        self.assertEqual(settings.defaults.clone_protocol, "https")

    def test_rejects_config_without_enabled_provider(self) -> None:
        with self.assertRaisesRegex(RemoteCatalogError, "At least one"):
            load_tui_settings({"tui": {"providers": {}}})


class CliTuiArgumentTests(unittest.TestCase):
    """CLI validation tests for --tui."""

    def test_tui_requires_config(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")

        with patch.object(sys, "argv", ["analyze_git_repo_loc", "--tui"]):
            with self.assertRaises(SystemExit) as ctx:
                parse_arguments(parser)

        self.assertEqual(ctx.exception.code, 2)

    def test_tui_config_allows_missing_repositories(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text(
                "settings:\n  output: ./out\n"
                "tui:\n"
                "  providers:\n"
                "    github:\n"
                "      enabled: true\n",
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                ["analyze_git_repo_loc", "--tui", "--config", str(config_path)],
            ):
                args = parse_arguments(parser)

        self.assertTrue(args.tui)
        self.assertIsNone(args.repo_paths)
        self.assertEqual(args.output, Path("./out"))


class RemoteCatalogTests(unittest.TestCase):
    """Provider API normalization tests."""

    def test_github_response_normalizes_repository_refs(self) -> None:
        payload = [
            {
                "full_name": "octo/example",
                "name": "example",
                "clone_url": "https://github.com/octo/example.git",
                "ssh_url": "git@github.com:octo/example.git",
                "html_url": "https://github.com/octo/example",
                "default_branch": "develop",
            }
        ]

        with patch.object(remote_catalog, "_request_json", return_value=payload):
            refs = fetch_github_repositories(
                api_base_url="https://api.github.com",
                token="secret",
            )

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].provider, "github")
        self.assertEqual(refs[0].full_name, "octo/example")
        self.assertEqual(refs[0].default_branch, "develop")

    def test_gitlab_response_normalizes_repository_refs(self) -> None:
        payload = [
            {
                "path_with_namespace": "team/example",
                "name": "example",
                "http_url_to_repo": "https://gitlab.com/team/example.git",
                "ssh_url_to_repo": "git@gitlab.com:team/example.git",
                "web_url": "https://gitlab.com/team/example",
                "default_branch": "main",
            }
        ]

        with patch.object(remote_catalog, "_request_json", return_value=payload):
            refs = fetch_gitlab_repositories(
                base_url="https://gitlab.com",
                token="secret",
            )

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].provider, "gitlab")
        self.assertEqual(refs[0].full_name, "team/example")
        self.assertEqual(refs[0].clone_url, "https://gitlab.com/team/example.git")

    def test_selected_refs_to_repo_paths_uses_clone_protocol(self) -> None:
        refs = [
            RemoteRepositoryRef(
                provider="github",
                name="example",
                full_name="octo/example",
                clone_url="https://github.com/octo/example.git",
                ssh_url="git@github.com:octo/example.git",
                web_url="https://github.com/octo/example",
                default_branch="develop",
            )
        ]

        entries = selected_refs_to_repo_paths(refs, clone_protocol="ssh")

        self.assertEqual(entries, [("git@github.com:octo/example.git", "develop", [])])

    def test_enabled_github_provider_requires_token(self) -> None:
        settings = load_tui_settings(
            {"tui": {"providers": {"github": {"enabled": True}}}}
        )

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RemoteCatalogError, "GITHUB_TOKEN"):
                fetch_remote_repositories(settings)

    def test_api_failure_is_wrapped_as_catalog_error(self) -> None:
        settings = load_tui_settings(
            {"tui": {"providers": {"github": {"enabled": True}}}}
        )

        with patch.dict("os.environ", {"GITHUB_TOKEN": "secret"}, clear=True):
            with patch.object(remote_catalog, "_request_json", side_effect=OSError("boom")):
                with self.assertRaisesRegex(RemoteCatalogError, "Failed to fetch"):
                    fetch_remote_repositories(settings)

    def test_empty_provider_result_is_catalog_error(self) -> None:
        settings = load_tui_settings(
            {"tui": {"providers": {"github": {"enabled": True}}}}
        )

        with patch.dict("os.environ", {"GITHUB_TOKEN": "secret"}, clear=True):
            with patch.object(remote_catalog, "_request_json", return_value=[]):
                with self.assertRaisesRegex(RemoteCatalogError, "No repositories"):
                    fetch_remote_repositories(settings)


class TuiStartupTests(unittest.TestCase):
    """TUI startup failure tests."""

    def test_tui_cancel_exits_before_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text(
                "tui:\n"
                "  providers:\n"
                "    github:\n"
                "      enabled: true\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(tui=True, config=config_path, repo_paths=None)

            with patch(
                "analyze_git_repo_loc.__main__.fetch_remote_repositories",
                return_value=[
                    RemoteRepositoryRef(
                        "github",
                        "alpha",
                        "org/alpha",
                        "https://a.git",
                        "",
                        "",
                        "main",
                    )
                ],
            ):
                with patch(
                    "analyze_git_repo_loc.__main__.run_repository_selector",
                    side_effect=TuiSelectionCancelled("cancelled"),
                ):
                    with self.assertRaises(SystemExit) as ctx:
                        _apply_tui_repository_selection(args)

        self.assertEqual(ctx.exception.code, 1)


class RepositorySelectorStateTests(unittest.TestCase):
    """Terminal-independent selector behavior tests."""

    def test_search_and_toggle_visible_selection(self) -> None:
        refs = [
            RemoteRepositoryRef("github", "alpha", "org/alpha", "https://a.git", "", "", "main"),
            RemoteRepositoryRef("gitlab", "beta", "team/beta", "https://b.git", "", "", "dev"),
        ]
        state = RepositorySelectorState(refs)

        state.set_query("beta")
        state.toggle_current()

        self.assertEqual(state.visible_refs, [refs[1]])
        self.assertEqual(state.selected_refs, [refs[1]])

    def test_cancel_marks_state_cancelled(self) -> None:
        state = RepositorySelectorState(
            [RemoteRepositoryRef("github", "alpha", "org/alpha", "https://a.git", "", "", "main")]
        )

        state.cancel()

        self.assertTrue(state.cancelled)


if __name__ == "__main__":
    unittest.main()
