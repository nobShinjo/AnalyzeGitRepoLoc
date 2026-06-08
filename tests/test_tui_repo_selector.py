"""Tests for the GitHub/GitLab repository selector TUI."""

from __future__ import annotations

# pylint: disable=missing-function-docstring

import argparse
from email.message import Message
import os
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from analyze_git_repo_loc.__main__ import _apply_interactive_repository_selection
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.interactive.tui_auth import (
    AuthChoice,
    AuthMethodStatus,
    build_auth_method_statuses,
    choose_auto_auth_status,
    get_cli_token,
    resolve_auth_choice,
    run_tui_auth_selection,
)
from analyze_git_repo_loc.interactive.tui_selector import (
    TuiSelectionCancelled,
)
from analyze_git_repo_loc.remote import remote_catalog
from analyze_git_repo_loc.remote import remote_oauth
from analyze_git_repo_loc.remote.remote_auth import (
    build_host_provider_env_var,
    build_host_token_env_var,
)
from analyze_git_repo_loc.remote.remote_catalog import (
    RemoteCatalogError,
    RemoteRepositoryRef,
    fetch_github_branches,
    fetch_github_repositories,
    fetch_gitlab_branches,
    fetch_gitlab_repositories,
    fetch_remote_repositories,
    load_tui_settings,
    selected_refs_to_repo_paths,
)
from analyze_git_repo_loc.remote.remote_oauth import (
    DeviceCodeLoginError,
    fetch_github_device_code_token,
    fetch_gitlab_device_code_token,
)
from analyze_git_repo_loc.utils import parse_arguments


class TuiConfigTests(unittest.TestCase):
    """Interactive config loading tests."""

    def test_loads_minimal_interactive_settings_without_optional_sections(self) -> None:
        config = {
            "interactive": {
                "providers": {
                    "github": {"enabled": True},
                }
            }
        }

        settings = load_tui_settings(config)

        self.assertTrue(settings.providers.github.enabled)
        self.assertFalse(settings.providers.gitlab.enabled)
        self.assertEqual(settings.providers.gitlab.base_url, "https://gitlab.com")
        self.assertEqual(settings.defaults.clone_protocol, "https")

    def test_loads_interactive_settings_with_defaults(self) -> None:
        config = {
            "interactive": {
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
        with patch("locale.getlocale", return_value=("en_US", "UTF-8")):
            with self.assertRaisesRegex(
                RemoteCatalogError,
                tr("doctor.error.provider_enabled_required", language="en"),
            ):
                load_tui_settings({"interactive": {"providers": {}}})

    def test_rejects_legacy_tui_settings_section(self) -> None:
        with patch("locale.getlocale", return_value=("en_US", "UTF-8")):
            with self.assertRaisesRegex(
                RemoteCatalogError,
                tr("doctor.error.interactive_providers_required", language="en"),
            ):
                load_tui_settings({"tui": {"providers": {"github": {"enabled": True}}}})

    def test_ignores_legacy_provider_auth_settings(self) -> None:
        settings = load_tui_settings(
            {
                "interactive": {
                    "providers": {
                        "github": {
                            "enabled": True,
                            "auth": {
                                "method": "device_code",
                                "client_id": "abc123",
                                "scopes": ["repo"],
                            },
                        }
                    }
                }
            }
        )

        self.assertTrue(settings.providers.github.enabled)
        self.assertFalse(hasattr(settings.providers.github, "auth"))


class CliTuiArgumentTests(unittest.TestCase):
    """CLI validation tests for interactive run subcommands."""

    def test_legacy_tui_flag_is_rejected(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")

        with patch.object(sys, "argv", ["analyze_git_repo_loc", "--tui"]):
            with self.assertRaises(SystemExit) as ctx:
                parse_arguments(parser)

        self.assertEqual(ctx.exception.code, 2)

    def test_interactive_run_config_allows_missing_repositories(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text(
                "settings:\n  output: ./out\n"
                "interactive:\n"
                "  providers:\n"
                "    github:\n"
                "      enabled: true\n",
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                ["analyze_git_repo_loc", "run", "-i", "--config", str(config_path)],
            ):
                args = parse_arguments(parser)

        self.assertEqual(args.command, "run")
        self.assertTrue(args.interactive)
        self.assertIsNone(args.repo_paths)
        self.assertEqual(args.output, Path("./out"))

    def test_long_interactive_run_flag_is_supported(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text(
                "settings:\n  output: ./out\n"
                "interactive:\n"
                "  providers:\n"
                "    github:\n"
                "      enabled: true\n",
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "analyze_git_repo_loc",
                    "run",
                    "--interactive",
                    "--config",
                    str(config_path),
                ],
            ):
                args = parse_arguments(parser)

        self.assertTrue(args.interactive)

    def test_run_defaults_to_non_interactive(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text(
                "settings:\n"
                "  output: ./out\n"
                "repositories:\n"
                "  - path: https://github.com/org/alpha.git\n"
                "    branch: main\n",
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                ["analyze_git_repo_loc", "run", "--config", str(config_path)],
            ):
                args = parse_arguments(parser)

        self.assertFalse(args.interactive)

    def test_tui_subcommand_is_rejected(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")

        with patch.object(sys, "argv", ["analyze_git_repo_loc", "tui"]):
            with self.assertRaises(SystemExit) as ctx:
                parse_arguments(parser)

        self.assertEqual(ctx.exception.code, 2)

    def test_wizard_subcommand_is_rejected(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")

        with patch.object(sys, "argv", ["analyze_git_repo_loc", "wizard"]):
            with self.assertRaises(SystemExit) as ctx:
                parse_arguments(parser)

        self.assertEqual(ctx.exception.code, 2)

    def test_config_repository_include_subpath_is_loaded(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text(
                "settings:\n"
                "  output: ./out\n"
                "repositories:\n"
                "  - path: https://github.com/org/alpha.git\n"
                "    branch: main\n"
                "    include_subpath: src/app\n"
                "    exclude_dirs:\n"
                "      - vendor\n",
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                ["analyze_git_repo_loc", "run", "--config", str(config_path)],
            ):
                args = parse_arguments(parser)

        self.assertEqual(args.command, "run")
        self.assertEqual(
            args.repo_paths,
            [("https://github.com/org/alpha.git", "main", ["vendor"], "src/app")],
        )

    def test_parse_arguments_restores_provider_hint_for_self_hosted_github(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text(
                "settings:\n"
                "  output: ./out\n"
                "repositories:\n"
                "  - path: https://git.example.com/org/alpha.git\n"
                "    branch: main\n"
                "interactive:\n"
                "  providers:\n"
                "    github:\n"
                "      enabled: true\n"
                "      api_base_url: https://git.example.com/api/v3\n",
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                with patch.object(
                    sys,
                    "argv",
                    ["analyze_git_repo_loc", "run", "--config", str(config_path)],
                ):
                    parse_arguments(parser)

                self.assertEqual(
                    os.environ[build_host_provider_env_var("git.example.com")],
                    "github",
                )

    def test_run_uses_default_config_yml(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                os.chdir(tmp_dir)
                Path("config.yml").write_text(
                    "settings:\n"
                    "  output: ./out\n"
                    "repositories:\n"
                    "  - path: https://github.com/org/alpha.git\n"
                    "    branch: main\n",
                    encoding="utf-8",
                )

                with patch.object(sys, "argv", ["analyze_git_repo_loc", "run"]):
                    args = parse_arguments(parser)
            finally:
                os.chdir(original_cwd)

        self.assertEqual(args.command, "run")
        self.assertEqual(args.config, Path("config.yml"))
        self.assertEqual(
            args.repo_paths,
            [("https://github.com/org/alpha.git", "main", [], None)],
        )

    def test_run_minimal_cli_overrides_config(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text(
                "settings:\n"
                "  output: ./out\n"
                "  interval: monthly\n"
                "repositories:\n"
                "  - path: https://github.com/org/alpha.git\n"
                "    branch: main\n",
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "analyze_git_repo_loc",
                    "run",
                    "--config",
                    str(config_path),
                    "--output",
                    "reports",
                    "--since",
                    "2026-01-01",
                    "--until",
                    "2026-05-01",
                    "--interval",
                    "weekly",
                    "--no-plot-show",
                ],
            ):
                args = parse_arguments(parser)

        self.assertEqual(args.output, Path("reports"))
        self.assertEqual(args.interval, "weekly")
        self.assertEqual(args.since.isoformat(), "2026-01-01T00:00:00")
        self.assertEqual(args.until.isoformat(), "2026-05-01T00:00:00")
        self.assertTrue(args.no_plot_show)

    def test_legacy_repo_paths_without_subcommand_is_rejected(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")

        with patch.object(sys, "argv", ["analyze_git_repo_loc", "."]):
            with self.assertRaises(SystemExit) as ctx:
                parse_arguments(parser)

        self.assertEqual(ctx.exception.code, 2)


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

    def test_github_branch_response_normalizes_names(self) -> None:
        payload = [{"name": "main"}, {"name": "feature/tui"}]

        with patch.object(remote_catalog, "_request_json", return_value=payload) as requester:
            branches = fetch_github_branches(
                api_base_url="https://api.github.com",
                full_name="octo/example",
                token="secret",
            )

        self.assertEqual(branches, ["main", "feature/tui"])
        requester.assert_called_once()
        self.assertIn("/repos/octo/example/branches", requester.call_args.args[0])

    def test_gitlab_branch_response_normalizes_names(self) -> None:
        payload = [{"name": "main"}, {"name": "release"}]

        with patch.object(remote_catalog, "_request_json", return_value=payload) as requester:
            branches = fetch_gitlab_branches(
                base_url="https://gitlab.example.com",
                full_name="team/example",
                token="secret",
            )

        self.assertEqual(branches, ["main", "release"])
        requester.assert_called_once()
        self.assertIn(
            "/api/v4/projects/team%2Fexample/repository/branches",
            requester.call_args.args[0],
        )

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

    def test_enabled_github_provider_requires_resolved_token(self) -> None:
        settings = load_tui_settings(
            {"interactive": {"providers": {"github": {"enabled": True}}}}
        )

        with self.assertRaisesRegex(RemoteCatalogError, "GitHub authentication"):
            fetch_remote_repositories(settings, auth_tokens={})

    def test_fetch_remote_repositories_uses_resolved_token(self) -> None:
        settings = load_tui_settings(
            {"interactive": {"providers": {"github": {"enabled": True}}}}
        )

        with patch.object(
            remote_catalog,
            "fetch_github_repositories",
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
        ) as fetcher:
            refs = fetch_remote_repositories(settings, auth_tokens={"github": "secret"})

        self.assertEqual(len(refs), 1)
        fetcher.assert_called_once_with(
            api_base_url="https://api.github.com",
            token="secret",
        )

    def test_api_failure_is_wrapped_as_catalog_error(self) -> None:
        settings = load_tui_settings(
            {"interactive": {"providers": {"github": {"enabled": True}}}}
        )

        with patch.object(remote_catalog, "_request_json", side_effect=OSError("boom")):
            with self.assertRaisesRegex(RemoteCatalogError, "Failed to fetch"):
                fetch_remote_repositories(settings, auth_tokens={"github": "secret"})

    def test_empty_provider_result_is_catalog_error(self) -> None:
        settings = load_tui_settings(
            {"interactive": {"providers": {"github": {"enabled": True}}}}
        )

        with patch.object(remote_catalog, "_request_json", return_value=[]):
            with self.assertRaisesRegex(RemoteCatalogError, "No repositories"):
                fetch_remote_repositories(settings, auth_tokens={"github": "secret"})


class TuiStartupTests(unittest.TestCase):
    """Interactive startup failure tests."""

    def test_interactive_cancel_exits_before_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text(
                "interactive:\n"
                "  providers:\n"
                "    github:\n"
                "      enabled: true\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(
                interactive=True,
                config=config_path,
                repo_paths=None,
            )

            with patch(
                "analyze_git_repo_loc.__main__.run_tui_wizard",
                side_effect=TuiSelectionCancelled("cancelled"),
            ):
                with self.assertRaises(SystemExit) as ctx:
                    _apply_interactive_repository_selection(args)

        self.assertEqual(ctx.exception.code, 1)


class TuiAuthTests(unittest.TestCase):
    """Runtime TUI authentication tests."""

    def test_build_auth_method_statuses_prioritizes_env_then_cli_then_device_then_token(
        self,
    ) -> None:
        statuses = build_auth_method_statuses(
            provider="github",
            base_url="https://api.github.com",
            env={"GITHUB_TOKEN": "env-token"},
            command_exists=lambda command: command == "gh",
            cli_token_getter=lambda provider, base_url: "cli-token",
            device_client_id_getter=lambda provider, base_url: "client",
        )

        self.assertEqual(
            [status.method for status in statuses],
            ["env_token", "cli", "device_code", "one_time_token"],
        )
        self.assertTrue(all(status.available for status in statuses))

    def test_choose_auto_auth_prefers_cli_when_env_missing(self) -> None:
        statuses = [
            AuthMethodStatus("env_token", "env", False, "missing"),
            AuthMethodStatus("cli", "gh", True, "logged in", token="cli-token"),
            AuthMethodStatus("device_code", "device", True, "available"),
            AuthMethodStatus("one_time_token", "paste", True, "available"),
        ]

        status = choose_auto_auth_status(statuses)

        assert status is not None
        self.assertEqual(status.method, "cli")

    def test_choose_auto_auth_skips_interactive_methods(self) -> None:
        statuses = [
            AuthMethodStatus("device_code", "device", True, "available"),
            AuthMethodStatus("one_time_token", "paste", True, "available"),
        ]

        self.assertIsNone(choose_auto_auth_status(statuses))

    def test_build_auth_method_statuses_marks_missing_cli_and_device_unavailable(
        self,
    ) -> None:
        statuses = build_auth_method_statuses(
            provider="github",
            base_url="https://api.github.com",
            env={},
            command_exists=lambda _: False,
            cli_token_getter=lambda provider, base_url: None,
            device_client_id_getter=lambda provider, base_url: None,
        )

        status_map = {status.method: status for status in statuses}

        self.assertFalse(status_map["env_token"].available)
        self.assertFalse(status_map["cli"].available)
        self.assertFalse(status_map["device_code"].available)
        self.assertTrue(status_map["one_time_token"].available)

    def test_gitlab_self_hosted_device_code_prompts_for_client_id(self) -> None:
        statuses = build_auth_method_statuses(
            provider="gitlab",
            base_url="https://gitlab.example.com",
            env={},
            command_exists=lambda _: False,
            cli_token_getter=lambda provider, base_url: None,
            device_client_id_getter=lambda provider, base_url: None,
        )

        status_map = {status.method: status for status in statuses}

        self.assertTrue(status_map["device_code"].available)
        self.assertIn("entered for this run", status_map["device_code"].detail)

    def test_resolve_auth_choice_uses_one_time_token_without_persisting(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            token = resolve_auth_choice(
                provider="github",
                base_url="https://api.github.com",
                choice=AuthChoice(method="one_time_token", token="typed-token"),
            )

            self.assertEqual(token, "typed-token")
            self.assertEqual(os.environ["GITHUB_TOKEN"], "typed-token")

    def test_resolve_auth_choice_uses_device_code_and_sets_process_env(self) -> None:
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}, clear=True):
            with patch(
                "analyze_git_repo_loc.interactive.tui_auth.fetch_github_device_code_token",
                return_value="web-token",
            ) as fetcher:
                token = resolve_auth_choice(
                    provider="github",
                    base_url="https://api.github.com",
                    choice=AuthChoice(method="device_code", client_id="client"),
                )

            self.assertEqual(token, "web-token")
            self.assertEqual(os.environ["GITHUB_TOKEN"], "web-token")
            fetcher.assert_called_once_with(
                client_id="client",
                scopes=("repo", "read:org"),
            )

    def test_resolve_auth_choice_requires_device_client_id(self) -> None:
        with self.assertRaisesRegex(DeviceCodeLoginError, "client_id"):
            resolve_auth_choice(
                provider="github",
                base_url="https://api.github.com",
                choice=AuthChoice(method="device_code"),
            )

    def test_get_cli_token_reads_github_cli_token(self) -> None:
        runner = Mock()
        runner.return_value = Mock(returncode=0, stdout="gh-token\n", stderr="")

        with patch(
            "analyze_git_repo_loc.remote.remote_auth.shutil.which",
            return_value="gh",
        ):
            token = get_cli_token("github", "https://api.github.com", runner=runner)

        self.assertEqual(token, "gh-token")
        runner.assert_called_once()
        self.assertEqual(
            runner.call_args.args[0],
            ["gh", "auth", "token", "--hostname", "github.com"],
        )

    def test_get_cli_token_reads_gitlab_status_token(self) -> None:
        runner = Mock()
        runner.return_value = Mock(
            returncode=0,
            stdout="gitlab.com\n  Token: glpat-token\n",
            stderr="",
        )

        with patch(
            "analyze_git_repo_loc.remote.remote_auth.shutil.which",
            return_value="glab",
        ):
            token = get_cli_token("gitlab", "https://gitlab.com", runner=runner)

        self.assertEqual(token, "glpat-token")
        runner.assert_called_once_with(
            ["glab", "auth", "status", "--hostname", "gitlab.com", "--show-token"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )

    def test_get_cli_token_returns_none_when_cli_is_missing(self) -> None:
        runner = Mock()

        with patch(
            "analyze_git_repo_loc.remote.remote_auth.shutil.which",
            return_value=None,
        ):
            token = get_cli_token("gitlab", "https://gitlab.com", runner=runner)

        self.assertIsNone(token)
        runner.assert_not_called()

    def test_get_cli_token_returns_none_for_utf8_decode_errors(self) -> None:
        runner = Mock(
            side_effect=UnicodeDecodeError("cp932", b"\x80", 0, 1, "invalid")
        )

        with patch(
            "analyze_git_repo_loc.remote.remote_auth.shutil.which",
            return_value="glab",
        ):
            token = get_cli_token("gitlab", "https://gitlab.com", runner=runner)

        self.assertIsNone(token)

    def test_get_cli_token_returns_none_for_subprocess_errors(self) -> None:
        runner = Mock(side_effect=subprocess.SubprocessError("failed"))

        with patch(
            "analyze_git_repo_loc.remote.remote_auth.shutil.which",
            return_value="gh",
        ):
            token = get_cli_token("github", "https://api.github.com", runner=runner)

        self.assertIsNone(token)

    def test_run_tui_auth_selection_sets_host_specific_token(self) -> None:
        settings = load_tui_settings(
            {
                "interactive": {
                    "providers": {
                        "gitlab": {
                            "enabled": True,
                            "base_url": "https://gitlab.example.com",
                        }
                    }
                }
            }
        )

        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "analyze_git_repo_loc.interactive.tui_auth.build_auth_method_statuses",
                return_value=[
                    AuthMethodStatus(
                        "cli",
                        "glab CLI login",
                        True,
                        "logged in",
                        token="host-token",
                    )
                ],
            ):
                tokens, labels = run_tui_auth_selection(settings, auto=True)

            self.assertEqual(tokens, {"gitlab": "host-token"})
            self.assertEqual(labels, {"gitlab": "glab"})
            self.assertEqual(
                os.environ[build_host_token_env_var("gitlab.example.com")],
                "host-token",
            )
            self.assertEqual(
                os.environ[build_host_provider_env_var("gitlab.example.com")],
                "gitlab",
            )


class DeviceCodeAuthTests(unittest.TestCase):
    """OAuth Device Code authentication tests."""

    def test_github_device_code_success_after_pending(self) -> None:
        responses = [
            {
                "device_code": "device",
                "user_code": "ABCD-1234",
                "verification_uri": "https://github.com/login/device",
                "interval": 5,
                "expires_in": 900,
            },
            {"error": "authorization_pending"},
            {"access_token": "token"},
        ]

        with patch(
            "analyze_git_repo_loc.remote.remote_oauth._post_form_json",
            side_effect=responses,
        ) as post:
            token = fetch_github_device_code_token(
                client_id="client",
                scopes=("repo",),
                notify=lambda _: None,
                sleep=lambda _: None,
            )

        self.assertEqual(token, "token")
        self.assertEqual(
            post.call_args_list[0].args[0],
            "https://github.com/login/device/code",
        )
        self.assertEqual(
            post.call_args_list[1].args[0],
            "https://github.com/login/oauth/access_token",
        )

    def test_github_device_code_slow_down_increases_poll_interval(self) -> None:
        responses = [
            {
                "device_code": "device",
                "user_code": "ABCD-1234",
                "verification_uri": "https://github.com/login/device",
                "interval": 5,
                "expires_in": 900,
            },
            {"error": "slow_down"},
            {"access_token": "token"},
        ]
        sleeps: list[float] = []

        with patch(
            "analyze_git_repo_loc.remote.remote_oauth._post_form_json",
            side_effect=responses,
        ):
            token = fetch_github_device_code_token(
                client_id="client",
                scopes=("repo",),
                notify=lambda _: None,
                sleep=sleeps.append,
            )

        self.assertEqual(token, "token")
        self.assertEqual(sleeps, [5, 10])

    def test_github_device_code_denied_and_expired_raise(self) -> None:
        for error in ("access_denied", "expired_token"):
            with self.subTest(error=error):
                responses = [
                    {
                        "device_code": "device",
                        "user_code": "ABCD-1234",
                        "verification_uri": "https://github.com/login/device",
                        "interval": 5,
                        "expires_in": 900,
                    },
                    {"error": error},
                ]
                with patch(
                    "analyze_git_repo_loc.remote.remote_oauth._post_form_json",
                    side_effect=responses,
                ):
                    with self.assertRaisesRegex(DeviceCodeLoginError, error):
                        fetch_github_device_code_token(
                            client_id="client",
                            scopes=("repo",),
                            notify=lambda _: None,
                            sleep=lambda _: None,
                        )

    def test_gitlab_device_code_uses_base_url_endpoints(self) -> None:
        responses = [
            {
                "device_code": "device",
                "user_code": "ABCD-1234",
                "verification_uri": "https://gitlab.example.com/device",
                "interval": 5,
                "expires_in": 900,
            },
            {"access_token": "token"},
        ]

        with patch(
            "analyze_git_repo_loc.remote.remote_oauth._post_form_json",
            side_effect=responses,
        ) as post:
            token = fetch_gitlab_device_code_token(
                base_url="https://gitlab.example.com",
                client_id="client",
                scopes=("read_api",),
                notify=lambda _: None,
                sleep=lambda _: None,
            )

        self.assertEqual(token, "token")
        self.assertEqual(
            post.call_args_list[0].args[0],
            "https://gitlab.example.com/oauth/authorize_device",
        )
        self.assertEqual(
            post.call_args_list[1].args[0],
            "https://gitlab.example.com/oauth/token",
        )

    def test_oauth_http_error_is_wrapped_as_device_login_error(self) -> None:
        error = HTTPError(
            "https://github.com/login/device/code",
            404,
            "Not Found",
            hdrs=Message(),
            fp=BytesIO(b'{"error":"not_found"}'),
        )

        with patch.object(remote_oauth, "urlopen", side_effect=error):
            with self.assertRaisesRegex(DeviceCodeLoginError, "HTTP 404"):
                # pylint: disable-next=protected-access
                remote_oauth._post_form_json(
                    "https://github.com/login/device/code",
                    {"client_id": "bad"},
                )


if __name__ == "__main__":
    unittest.main()
