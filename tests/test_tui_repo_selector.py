"""Tests for the GitHub/GitLab repository selector TUI."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from analyze_git_repo_loc import remote_catalog
from analyze_git_repo_loc import remote_oauth
from analyze_git_repo_loc import tui_wizard
from analyze_git_repo_loc import utils
from analyze_git_repo_loc.__main__ import _apply_interactive_repository_selection
from analyze_git_repo_loc.__main__ import _format_output_summary
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.remote_catalog import (
    RemoteCatalogError,
    RemoteRepositoryRef,
    fetch_github_repositories,
    fetch_gitlab_repositories,
    fetch_remote_repositories,
    load_tui_settings,
    selected_refs_to_repo_paths,
)
from analyze_git_repo_loc.remote_auth import build_host_token_env_var
from analyze_git_repo_loc.tui_auth import run_tui_auth_selection
from analyze_git_repo_loc.remote_oauth import (
    DeviceCodeLoginError,
    fetch_github_device_code_token,
    fetch_gitlab_device_code_token,
)
from analyze_git_repo_loc.tui_auth import (
    AuthChoice,
    AuthMethodStatus,
    build_auth_method_statuses,
    choose_auto_auth_status,
    get_cli_token,
    resolve_auth_choice,
)
from analyze_git_repo_loc.tui_selector import (
    RepositorySelectorState,
    TuiSelectionCancelled,
)
from analyze_git_repo_loc.tui_wizard import (
    ProviderTarget,
    SelectedRepositoryConfig,
    TuiWizardState,
    apply_branch_selection,
    apply_repository_overrides,
    apply_wizard_state,
    build_lightweight_recommendations,
    build_provider_candidates,
    choose_auto_provider_targets,
    format_compact_list,
    load_quick_defaults,
    normalize_final_action,
    render_final_review,
    selected_targets_to_settings,
    wizard_state_to_config,
)
from analyze_git_repo_loc.utils import parse_arguments


class TuiConfigTests(unittest.TestCase):
    """Interactive config loading tests."""

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
        with self.assertRaisesRegex(RemoteCatalogError, "At least one"):
            load_tui_settings({"interactive": {"providers": {}}})

    def test_rejects_legacy_tui_settings_section(self) -> None:
        with self.assertRaisesRegex(RemoteCatalogError, "interactive.providers"):
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

        self.assertIsNotNone(status)
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
                "analyze_git_repo_loc.tui_auth.fetch_github_device_code_token",
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

        token = get_cli_token("gitlab", "https://gitlab.com", runner=runner)

        self.assertEqual(token, "glpat-token")
        self.assertEqual(
            runner.call_args.args[0],
            ["glab", "auth", "status", "--hostname", "gitlab.com", "--show-token"],
        )

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
                "analyze_git_repo_loc.tui_auth.build_auth_method_statuses",
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
            "analyze_git_repo_loc.remote_oauth._post_form_json",
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
            "analyze_git_repo_loc.remote_oauth._post_form_json",
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
                    "analyze_git_repo_loc.remote_oauth._post_form_json",
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
            "analyze_git_repo_loc.remote_oauth._post_form_json",
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
            hdrs=None,
            fp=BytesIO(b'{"error":"not_found"}'),
        )

        with patch.object(remote_oauth, "urlopen", side_effect=error):
            with self.assertRaisesRegex(DeviceCodeLoginError, "HTTP 404"):
                remote_oauth._post_form_json(
                    "https://github.com/login/device/code",
                    {"client_id": "bad"},
                )


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


class TuiWizardStateTests(unittest.TestCase):
    """Terminal-independent full wizard state tests."""

    def test_load_quick_defaults_reads_non_secret_interactive_presets(self) -> None:
        defaults = load_quick_defaults(
            {
                "interactive": {
                    "quick_defaults": {
                        "interval": "weekly",
                        "lang": ["Python", "Markdown"],
                        "exclude_dirs": "node_modules,.venv",
                        "cache_policy": "update",
                        "no_plot_show": True,
                    }
                }
            }
        )

        self.assertEqual(defaults.interval, "weekly")
        self.assertEqual(defaults.lang, ["Python", "Markdown"])
        self.assertEqual(defaults.exclude_dirs, ["node_modules", ".venv"])
        self.assertEqual(defaults.cache_policy, "update")
        self.assertTrue(defaults.no_plot_show)

    def test_quick_run_skips_full_edit_prompts(self) -> None:
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[],
            selected_repositories=[],
        )

        with patch(
            "analyze_git_repo_loc.tui_wizard._prompt_final_action",
            return_value="run",
        ):
            with patch("analyze_git_repo_loc.tui_wizard._prompt_branch_selection") as branch:
                with patch("analyze_git_repo_loc.tui_wizard._prompt_analysis_scope") as scope:
                    with patch("analyze_git_repo_loc.tui_wizard._prompt_path_rules") as path:
                        with patch(
                            "analyze_git_repo_loc.tui_wizard._prompt_output_cache_display"
                        ) as output:
                            action = tui_wizard._run_wizard_steps(state)

        self.assertEqual(action, "run")
        branch.assert_not_called()
        scope.assert_not_called()
        path.assert_not_called()
        output.assert_not_called()

    def test_lightweight_recommendations_scan_only_existing_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "out"
            cached_repo = output / ".cache" / "remote-repos" / "alpha-123"
            cached_repo.mkdir(parents=True)
            (cached_repo / ".git").mkdir()
            (cached_repo / "src").mkdir()
            (cached_repo / "src" / "app.py").write_text("print('hi')", encoding="utf-8")
            (cached_repo / "README.md").write_text("# hi", encoding="utf-8")
            (cached_repo / "node_modules").mkdir()
            (cached_repo / "node_modules" / "ignored.js").write_text("x", encoding="utf-8")

            ref = RemoteRepositoryRef(
                "github",
                "alpha",
                "org/alpha",
                "https://github.com/org/alpha.git",
                "",
                "https://github.com/org/alpha",
                "main",
            )
            state = TuiWizardState(
                provider_targets=[],
                auth_tokens={},
                repository_catalog=[ref],
                selected_repositories=[
                    SelectedRepositoryConfig(ref=ref, branch="main", cache_status="cached")
                ],
                output=output,
            )

            with patch(
                "analyze_git_repo_loc.tui_wizard.determine_cache_path",
                return_value=cached_repo,
            ):
                recommendations = build_lightweight_recommendations(state)

        self.assertEqual(recommendations.languages[:2], ["Markdown", "Python"])
        self.assertIn("node_modules", recommendations.exclude_dirs)
        self.assertEqual(recommendations.language_source, "existing cache")

    def test_repo_progress_bars_accept_include_subpath_entries(self) -> None:
        progress = Mock(pos=0)
        bar = Mock()

        with patch("analyze_git_repo_loc.utils.tqdm", return_value=bar):
            repo_bars, repo_labels = utils._build_repo_progress_bars(
                [("https://github.com/org/alpha.git", "main", [], "src")],
                progress=progress,
                label_width=20,
            )

        self.assertEqual(repo_bars, {0: bar})
        self.assertEqual(repo_labels, {0: "alpha"})

    def test_provider_candidates_include_github_gitlab_dotcom_and_self_hosted(
        self,
    ) -> None:
        settings = load_tui_settings(
            {
                "interactive": {
                    "providers": {
                        "github": {"enabled": True},
                        "gitlab": {
                            "enabled": True,
                            "base_url": "https://gitlab.example.com",
                        },
                    }
                }
            }
        )

        candidates = build_provider_candidates(settings)

        self.assertEqual(
            [(candidate.key, candidate.label) for candidate in candidates],
            [
                ("github", "GitHub"),
                ("gitlab.com", "GitLab.com"),
                ("gitlab.self_hosted", "Self-hosted GitLab"),
            ],
        )
        self.assertEqual(candidates[2].base_url, "https://gitlab.example.com")

    def test_choose_auto_provider_targets_returns_single_enabled_provider(self) -> None:
        settings = load_tui_settings(
            {"interactive": {"providers": {"github": {"enabled": True}}}}
        )

        targets = choose_auto_provider_targets(settings)

        self.assertIsNotNone(targets)
        self.assertEqual([target.key for target in targets or []], ["github"])

    def test_choose_auto_provider_targets_returns_none_for_multiple_providers(self) -> None:
        settings = load_tui_settings(
            {
                "interactive": {
                    "providers": {
                        "github": {"enabled": True},
                        "gitlab": {"enabled": True},
                    }
                }
            }
        )

        self.assertIsNone(choose_auto_provider_targets(settings))

    def test_selected_provider_targets_build_runtime_settings(self) -> None:
        settings = selected_targets_to_settings(
            [
                ProviderTarget(
                    key="github",
                    provider="github",
                    label="GitHub",
                    base_url="https://api.github.com",
                ),
                ProviderTarget(
                    key="gitlab.self_hosted",
                    provider="gitlab",
                    label="Self-hosted GitLab",
                    base_url="https://gitlab.example.com",
                ),
            ],
            clone_protocol="ssh",
        )

        self.assertTrue(settings.providers.github.enabled)
        self.assertTrue(settings.providers.gitlab.enabled)
        self.assertEqual(settings.providers.gitlab.base_url, "https://gitlab.example.com")
        self.assertEqual(settings.defaults.clone_protocol, "ssh")

    def test_apply_wizard_state_updates_args_for_existing_pipeline(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "git@github.com:org/alpha.git",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={"github": "secret"},
            repository_catalog=[ref],
            selected_repositories=[
                SelectedRepositoryConfig(
                    ref=ref,
                    branch="develop",
                    include_subpath="src",
                    exclude_dirs=["generated"],
                )
            ],
            clone_protocol="ssh",
            interval="weekly",
            lang=["Python"],
            author_name=["Nob"],
            workers=2,
            global_exclude_dirs=["vendor"],
            output=Path("out"),
            clear_cache=True,
            no_plot_show=True,
        )
        args = argparse.Namespace()

        apply_wizard_state(args, state)

        self.assertEqual(
            args.repo_paths,
            [
                (
                    "git@github.com:org/alpha.git",
                    "develop",
                    ["vendor", "generated"],
                    "src",
                    None,
                    None,
                )
            ],
        )
        self.assertEqual(args.interval, "weekly")
        self.assertEqual(args.lang, ["Python"])
        self.assertEqual(args.author_name, ["Nob"])
        self.assertEqual(args.workers, 2)
        self.assertIsNone(args.exclude_dirs)
        self.assertTrue(args.clear_cache)
        self.assertTrue(args.no_plot_show)

    def test_apply_wizard_state_keeps_missing_template_ready_excludes(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[ref],
            selected_repositories=[
                SelectedRepositoryConfig(ref=ref, branch="main", cache_status="cached")
            ],
            global_exclude_dirs=["node_modules", ".venv"],
            output=Path("out"),
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            cached_repo = Path(tmp_dir) / "cache" / "alpha"
            (cached_repo / "node_modules").mkdir(parents=True)
            with patch(
                "analyze_git_repo_loc.tui_wizard.determine_cache_path",
                return_value=cached_repo,
            ):
                args = apply_wizard_state(argparse.Namespace(), state)

        self.assertEqual(args.repo_paths[0][2], ["node_modules", ".venv"])

    def test_include_subpath_rejects_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "repo"
            root.mkdir()

            with self.assertRaisesRegex(ValueError, "repository-root-relative"):
                utils._apply_include_subpath(root, root / "outside")

    def test_include_subpath_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "repo"
            root.mkdir()

            with self.assertRaisesRegex(ValueError, "within repository root"):
                utils._apply_include_subpath(root, "../outside")

    def test_format_compact_list_limits_noisy_recommendations(self) -> None:
        formatted = format_compact_list(
            ["Markdown", "Python", "YAML", "JSON", "C#", "JavaScript"],
            limit=3,
        )

        self.assertEqual(formatted, "Markdown, Python, YAML (+3 more)")

    def test_branch_and_repository_overrides_support_bulk_then_individual(self) -> None:
        ref = RemoteRepositoryRef(
            "gitlab",
            "beta",
            "team/beta",
            "https://gitlab.com/team/beta.git",
            "",
            "https://gitlab.com/team/beta",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[ref],
            selected_repositories=[SelectedRepositoryConfig(ref=ref, branch="main")],
        )

        apply_branch_selection(state, "develop")
        apply_repository_overrides(
            state,
            {
                "team/beta": {
                    "branch": "release",
                    "include_subpath": "packages/api",
                    "exclude_dirs": "dist,.cache",
                }
            },
        )

        repository = state.selected_repositories[0]
        self.assertEqual(repository.branch, "release")
        self.assertEqual(repository.include_subpath, "packages/api")
        self.assertEqual(repository.exclude_dirs, ["dist", ".cache"])

    def test_config_export_omits_auth_tokens(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={"github": "secret"},
            repository_catalog=[ref],
            selected_repositories=[SelectedRepositoryConfig(ref=ref, branch="main")],
            output=Path("out"),
        )

        exported = wizard_state_to_config(state)
        rendered = str(exported)

        self.assertNotIn("secret", rendered)
        self.assertEqual(exported["repositories"][0]["path"], "https://github.com/org/alpha.git")
        self.assertEqual(exported["settings"]["no_plot_show"], True)
        self.assertEqual(
            exported["interactive"]["quick_defaults"]["cache_policy"],
            "use",
        )
        self.assertNotIn("tui", exported)
        self.assertNotIn("auth_tokens", rendered)

    def test_fetch_repository_catalog_wraps_provider_errors(self) -> None:
        target = ProviderTarget(
            key="github",
            provider="github",
            label="GitHub",
            base_url="https://api.github.com",
        )

        with patch(
            "analyze_git_repo_loc.tui_wizard.fetch_github_repositories",
            side_effect=OSError("dns failed"),
        ):
            with self.assertRaisesRegex(RemoteCatalogError, "Failed to fetch GitHub"):
                tui_wizard._fetch_repository_catalog([target], {"github": "token"})

    def test_final_review_includes_key_execution_conditions(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[ref],
            selected_repositories=[
                SelectedRepositoryConfig(ref=ref, branch="main", cache_status="cached")
            ],
            interval="monthly",
            output=Path("out"),
            no_plot_show=True,
        )

        review = render_final_review(state, detailed=True)

        self.assertIn("1 repo | monthly", review)
        self.assertIn(tr("tui.interval", value="monthly"), review)
        self.assertIn("cache=cached", review)
        self.assertIn(tr("tui.auto_display", value=tr("tui.off")), review)

    def test_compact_final_review_hides_repository_detail(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[
                ProviderTarget("github", "github", "GitHub", "https://api.github.com")
            ],
            auth_tokens={},
            auth_labels={"github": "gh"},
            repository_catalog=[ref],
            selected_repositories=[
                SelectedRepositoryConfig(ref=ref, branch="main", cache_status="cached")
            ],
            recommendations=tui_wizard.LightweightRecommendations(
                languages=["Markdown", "Python", "YAML", "JSON", "Bourne Shell", "TOML"],
                language_source="existing cache",
            ),
        )

        review = render_final_review(state)

        self.assertIn("GitHub via gh | 1 repo | monthly", review)
        self.assertIn(
            tr(
                "tui.suggestions",
                value="Markdown, Python, YAML, JSON, Bourne Shell (+1 more)",
                source="existing cache",
            ),
            review,
        )
        self.assertIn(tr("tui.final_actions").split("   ")[0], review)
        self.assertNotIn(tr("tui.repositories"), review)
        self.assertNotIn("cache=cached", review)

    def test_normalize_final_action_supports_short_keys(self) -> None:
        self.assertEqual(normalize_final_action(""), "run")
        self.assertEqual(normalize_final_action("e"), "edit")
        self.assertEqual(normalize_final_action("details"), "details")
        self.assertEqual(normalize_final_action("s"), "save")
        self.assertEqual(normalize_final_action("c"), "cancel")
        self.assertIsNone(normalize_final_action("wat"))

    def test_final_review_color_mode_emits_ansi_sequences(self) -> None:
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[],
            selected_repositories=[],
        )

        review = render_final_review(state, color=True)

        self.assertIn("\x1b[", review)


class CliOutputSummaryTests(unittest.TestCase):
    """CLI output summary formatting tests."""

    def test_format_output_summary_lists_artifacts(self) -> None:
        lines = _format_output_summary(Path("out/20260520123456"))

        self.assertIn(tr("output.finished"), lines)
        self.assertIn("Report: out\\20260520123456\\report.html", lines)
        self.assertIn("Summary: out\\20260520123456\\summary.md", lines)
        self.assertIn("Data: out\\20260520123456\\*.csv", lines)


if __name__ == "__main__":
    unittest.main()
