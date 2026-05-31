"""Tests for preflight doctor diagnostics."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from analyze_git_repo_loc.doctor import (
    DiagnosticResult,
    format_diagnostic_report,
    run_config_diagnostics,
    run_data_diagnostics,
)
from analyze_git_repo_loc.i18n import set_language_override, tr
from analyze_git_repo_loc.remote_catalog import RemoteRepositoryRef
from analyze_git_repo_loc.tui_auth import AuthMethodStatus


class DoctorDiagnosticsTests(unittest.TestCase):
    """Configuration doctor behavior tests."""

    def tearDown(self) -> None:
        set_language_override(None)

    def test_missing_config_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_config_diagnostics(Path(tmp) / "missing.yml")

        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.exit_code(), 1)

    def test_valid_local_repository_config_has_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            config = root / "config.yml"
            config.write_text(
                yaml.safe_dump(
                    {
                        "settings": {"interval": "weekly", "output": "reports"},
                        "repositories": [{"path": str(repo)}],
                    }
                ),
                encoding="utf-8",
            )

            result = run_config_diagnostics(config)

        self.assertEqual(result.issues, [])

    def test_missing_repository_path_is_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.yml"
            config.write_text(
                yaml.safe_dump({"repositories": [{"path": "missing"}]}),
                encoding="utf-8",
            )

            result = run_config_diagnostics(config)

        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.exit_code(), 0)
        self.assertEqual(result.exit_code(strict=True), 1)

    def test_missing_local_bare_repository_path_is_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.yml"
            config.write_text(
                yaml.safe_dump({"repositories": [{"path": "/srv/mirror.git"}]}),
                encoding="utf-8",
            )

            result = run_config_diagnostics(config)

        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.exit_code(), 0)
        self.assertEqual(result.exit_code(strict=True), 1)

    def test_secret_like_yaml_key_is_error(self) -> None:
        set_language_override("en")
        result = run_data_diagnostics(
            {
                "settings": {},
                "repositories": [{"path": "https://example.com/repo.git"}],
                "interactive": {"providers": {"github": {"token": "secret"}}},
            }
        )

        self.assertTrue(
            any(
                tr("doctor.error.secret_key", language="en", path="interactive.providers.github.token")
                == issue.message
                for issue in result.errors
            )
        )

    def test_remote_is_opt_in(self) -> None:
        config = {
            "settings": {},
            "interactive": {
                "providers": {
                    "github": {"enabled": True},
                    "gitlab": {"enabled": False},
                },
                "defaults": {"clone_protocol": "https"},
            },
        }
        with patch("analyze_git_repo_loc.doctor.fetch_remote_repositories") as fetch:
            result = run_data_diagnostics(config, remote=False)

        fetch.assert_not_called()
        self.assertEqual(result.errors, [])

    def test_remote_fetch_uses_provider_token(self) -> None:
        config = {
            "settings": {},
            "interactive": {
                "providers": {
                    "github": {"enabled": True, "api_base_url": "https://api.github.com"},
                    "gitlab": {"enabled": False},
                },
                "defaults": {"clone_protocol": "https"},
            },
        }
        with patch.dict("os.environ", {"GITHUB_TOKEN": "token"}, clear=True):
            with patch(
                "analyze_git_repo_loc.doctor.fetch_remote_repositories",
                return_value=[
                    RemoteRepositoryRef(
                        provider="github",
                        name="repo",
                        full_name="owner/repo",
                        clone_url="https://github.com/owner/repo.git",
                        ssh_url="git@github.com:owner/repo.git",
                        web_url="https://github.com/owner/repo",
                        default_branch="main",
                    )
                ],
            ) as fetch:
                result = run_data_diagnostics(config, remote=True)

        fetch.assert_called_once()
        self.assertEqual(result.errors, [])

    def test_remote_fetch_uses_cli_login_token(self) -> None:
        config = {
            "settings": {},
            "interactive": {
                "providers": {
                    "github": {"enabled": True, "api_base_url": "https://api.github.com"},
                    "gitlab": {"enabled": False},
                },
                "defaults": {"clone_protocol": "https"},
            },
        }
        with patch(
            "analyze_git_repo_loc.doctor.build_auth_method_statuses",
            return_value=[
                AuthMethodStatus(
                    method="cli",
                    label="gh CLI login",
                    available=True,
                    detail="logged in",
                    token="cli-token",
                )
            ],
        ):
            with patch(
                "analyze_git_repo_loc.doctor.fetch_remote_repositories",
                return_value=[
                    RemoteRepositoryRef(
                        provider="github",
                        name="repo",
                        full_name="owner/repo",
                        clone_url="https://github.com/owner/repo.git",
                        ssh_url="git@github.com:owner/repo.git",
                        web_url="https://github.com/owner/repo",
                        default_branch="main",
                    )
                ],
            ) as fetch:
                result = run_data_diagnostics(config, remote=True)

        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.kwargs["auth_tokens"]["github"], "cli-token")
        self.assertEqual(result.errors, [])

    def test_format_success_report(self) -> None:
        set_language_override("en")
        report = format_diagnostic_report(DiagnosticResult())

        self.assertIn(tr("doctor.report_title", language="en"), report)
        self.assertIn(tr("doctor.report_success", language="en"), report)

    def test_format_success_report_uses_japanese_translation(self) -> None:
        set_language_override("jp")

        report = format_diagnostic_report(DiagnosticResult())

        self.assertIn(tr("doctor.report_title", language="jp"), report)
        self.assertIn(tr("doctor.report_success", language="jp"), report)

    def test_remote_reports_missing_repository(self) -> None:
        set_language_override("en")
        config = {
            "settings": {},
            "repositories": [
                {
                    "path": "https://github.com/owner/missing.git",
                    "branch": "main",
                }
            ],
            "interactive": {
                "providers": {
                    "github": {"enabled": True, "api_base_url": "https://api.github.com"},
                    "gitlab": {"enabled": False},
                },
                "defaults": {"clone_protocol": "https"},
            },
        }
        with patch(
            "analyze_git_repo_loc.doctor.build_auth_method_statuses",
            return_value=[
                AuthMethodStatus(
                    method="cli",
                    label="gh CLI login",
                    available=True,
                    detail="logged in",
                    token="cli-token",
                )
            ],
        ):
            with patch(
                "analyze_git_repo_loc.doctor.fetch_remote_repositories",
                return_value=[
                    RemoteRepositoryRef(
                        provider="github",
                        name="repo",
                        full_name="owner/repo",
                        clone_url="https://github.com/owner/repo.git",
                        ssh_url="git@github.com:owner/repo.git",
                        web_url="https://github.com/owner/repo",
                        default_branch="main",
                    )
                ],
            ):
                result = run_data_diagnostics(config, remote=True)

        self.assertTrue(
            any(
                tr(
                    "doctor.error.remote_repo_missing",
                    language="en",
                    path="https://github.com/owner/missing.git",
                )
                == issue.message
                for issue in result.errors
            )
        )

    def test_remote_ignores_local_bare_repository_path(self) -> None:
        config = {
            "settings": {},
            "repositories": [
                {
                    "path": "/srv/mirror.git",
                    "branch": "main",
                }
            ],
            "interactive": {
                "providers": {
                    "github": {"enabled": True, "api_base_url": "https://api.github.com"},
                    "gitlab": {"enabled": False},
                },
                "defaults": {"clone_protocol": "https"},
            },
        }
        with patch(
            "analyze_git_repo_loc.doctor.build_auth_method_statuses",
            return_value=[
                AuthMethodStatus(
                    method="cli",
                    label="gh CLI login",
                    available=True,
                    detail="logged in",
                    token="cli-token",
                )
            ],
        ):
            with patch(
                "analyze_git_repo_loc.doctor.fetch_remote_repositories",
                return_value=[],
            ):
                result = run_data_diagnostics(config, remote=True)

        self.assertEqual(result.errors, [])

    def test_remote_reports_missing_branch(self) -> None:
        set_language_override("en")
        config = {
            "settings": {},
            "repositories": [
                {
                    "path": "https://github.com/owner/repo.git",
                    "branch": "release",
                }
            ],
            "interactive": {
                "providers": {
                    "github": {"enabled": True, "api_base_url": "https://api.github.com"},
                    "gitlab": {"enabled": False},
                },
                "defaults": {"clone_protocol": "https"},
            },
        }
        remote_ref = RemoteRepositoryRef(
            provider="github",
            name="repo",
            full_name="owner/repo",
            clone_url="https://github.com/owner/repo.git",
            ssh_url="git@github.com:owner/repo.git",
            web_url="https://github.com/owner/repo",
            default_branch="main",
        )
        with patch(
            "analyze_git_repo_loc.doctor.build_auth_method_statuses",
            return_value=[
                AuthMethodStatus(
                    method="cli",
                    label="gh CLI login",
                    available=True,
                    detail="logged in",
                    token="cli-token",
                )
            ],
        ):
            with patch(
                "analyze_git_repo_loc.doctor.fetch_remote_repositories",
                return_value=[remote_ref],
            ):
                with patch(
                    "analyze_git_repo_loc.doctor._fetch_remote_branches",
                    return_value=["main", "develop"],
                ):
                    result = run_data_diagnostics(config, remote=True)

        self.assertTrue(
            any(
                tr(
                    "doctor.error.remote_branch_missing",
                    language="en",
                    branch="release",
                    repository="owner/repo",
                )
                == issue.message
                for issue in result.errors
            )
        )

    def test_invalid_clone_protocol_is_translated_in_japanese(self) -> None:
        set_language_override("jp")
        config = {
            "settings": {},
            "interactive": {
                "providers": {
                    "github": {"enabled": True},
                    "gitlab": {"enabled": False},
                },
                "defaults": {"clone_protocol": "ftp"},
            },
        }

        result = run_data_diagnostics(config, remote=False)

        self.assertTrue(
            any(
                tr("doctor.error.clone_protocol", language="jp") == issue.message
                for issue in result.errors
            )
        )

    def test_remote_repository_check_runs_even_when_other_errors_exist(self) -> None:
        set_language_override("en")
        config = {
            "settings": {"interval": "yearly"},
            "repositories": [
                {
                    "path": "https://github.com/owner/missing.git",
                    "branch": "main",
                }
            ],
            "interactive": {
                "providers": {
                    "github": {"enabled": True, "api_base_url": "https://api.github.com"},
                    "gitlab": {"enabled": False},
                },
                "defaults": {"clone_protocol": "https"},
            },
        }

        with patch(
            "analyze_git_repo_loc.doctor.build_auth_method_statuses",
            return_value=[
                AuthMethodStatus(
                    method="cli",
                    label="gh CLI login",
                    available=True,
                    detail="logged in",
                    token="cli-token",
                )
            ],
        ):
            with patch(
                "analyze_git_repo_loc.doctor.fetch_remote_repositories",
                return_value=[
                    RemoteRepositoryRef(
                        provider="github",
                        name="repo",
                        full_name="owner/repo",
                        clone_url="https://github.com/owner/repo.git",
                        ssh_url="git@github.com:owner/repo.git",
                        web_url="https://github.com/owner/repo",
                        default_branch="main",
                    )
                ],
            ):
                result = run_data_diagnostics(config, remote=True)

        self.assertTrue(
            any(tr("doctor.error.interval", language="en") == issue.message for issue in result.errors)
        )
        self.assertTrue(
            any(
                tr(
                    "doctor.error.remote_repo_missing",
                    language="en",
                    path="https://github.com/owner/missing.git",
                )
                == issue.message
                for issue in result.errors
            )
        )

    def test_remote_repository_check_runs_even_with_invalid_clone_protocol(self) -> None:
        set_language_override("en")
        config = {
            "settings": {},
            "repositories": [
                {
                    "path": "https://github.com/owner/missing.git",
                    "branch": "main",
                }
            ],
            "interactive": {
                "providers": {
                    "github": {"enabled": True, "api_base_url": "https://api.github.com"},
                    "gitlab": {"enabled": False},
                },
                "defaults": {"clone_protocol": "ftp"},
            },
        }

        with patch(
            "analyze_git_repo_loc.doctor.build_auth_method_statuses",
            return_value=[
                AuthMethodStatus(
                    method="cli",
                    label="gh CLI login",
                    available=True,
                    detail="logged in",
                    token="cli-token",
                )
            ],
        ):
            with patch(
                "analyze_git_repo_loc.doctor.fetch_remote_repositories",
                return_value=[
                    RemoteRepositoryRef(
                        provider="github",
                        name="repo",
                        full_name="owner/repo",
                        clone_url="https://github.com/owner/repo.git",
                        ssh_url="git@github.com:owner/repo.git",
                        web_url="https://github.com/owner/repo",
                        default_branch="main",
                    )
                ],
            ):
                result = run_data_diagnostics(config, remote=True)

        self.assertTrue(
            any(tr("doctor.error.clone_protocol", language="en") == issue.message for issue in result.errors)
        )
        self.assertTrue(
            any(
                tr(
                    "doctor.error.remote_repo_missing",
                    language="en",
                    path="https://github.com/owner/missing.git",
                )
                == issue.message
                for issue in result.errors
            )
        )


class DoctorCliParserTests(unittest.TestCase):
    """Doctor command parser behavior tests."""

    def test_doctor_parser_defaults(self) -> None:
        import argparse
        import sys

        from analyze_git_repo_loc.utils import parse_arguments

        parser = argparse.ArgumentParser()
        with patch.object(sys, "argv", ["analyze_git_repo_loc", "doctor"]):
            args = parse_arguments(parser)

        self.assertEqual(args.command, "doctor")
        self.assertEqual(args.config, Path("config.yml"))
        self.assertFalse(args.remote)
        self.assertFalse(args.strict)
