"""Tests for first-run config initialization."""

from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from analyze_git_repo_loc.__main__ import _format_output_summary
from analyze_git_repo_loc.init_config import (
    InitConfigOptions,
    build_init_config_data,
    render_init_config_yaml,
    resolve_init_config_path,
)
from analyze_git_repo_loc.utils import parse_arguments


class InitConfigGenerationTests(unittest.TestCase):
    """Config data and YAML rendering tests."""

    def test_builds_minimal_tui_ready_config_without_repositories_or_secrets(
        self,
    ) -> None:
        options = InitConfigOptions(
            github_enabled=True,
            gitlab_enabled=False,
            output=Path("out"),
            interval="monthly",
            since="2024-01-01",
            until="2026-05-31",
            no_plot_show=True,
            cache_policy="use",
            exclude_dirs=["node_modules", ".venv"],
        )

        config = build_init_config_data(options)

        self.assertNotIn("repositories", config)
        self.assertEqual(config["settings"]["output"], "out")
        self.assertEqual(config["settings"]["interval"], "monthly")
        self.assertEqual(config["settings"]["since"], "2024-01-01")
        self.assertEqual(config["settings"]["until"], "2026-05-31")
        self.assertTrue(config["settings"]["no_plot_show"])
        self.assertFalse(config["settings"]["clear_cache"])
        self.assertTrue(config["tui"]["providers"]["github"]["enabled"])
        self.assertFalse(config["tui"]["providers"]["gitlab"]["enabled"])
        self.assertEqual(
            config["tui"]["quick_defaults"]["exclude_dirs"],
            ["node_modules", ".venv"],
        )
        rendered = repr(config)
        self.assertNotIn("TOKEN", rendered)
        self.assertNotIn("client_id", rendered)
        self.assertNotIn("auth", rendered)

    def test_render_init_config_yaml_round_trips_with_yaml_parser(self) -> None:
        config = build_init_config_data(
            InitConfigOptions(
                github_enabled=True,
                gitlab_enabled=True,
                output=Path("reports"),
                interval="weekly",
                since=None,
                until=None,
                no_plot_show=False,
                cache_policy="clear",
                exclude_dirs=[],
            )
        )

        rendered = render_init_config_yaml(config)
        loaded = yaml.safe_load(rendered)

        self.assertEqual(loaded, config)
        self.assertTrue(rendered.endswith("\n"))
        self.assertNotIn("repositories:", rendered)


class InitConfigPathTests(unittest.TestCase):
    """Config path selection safety tests."""

    def test_uses_default_config_path_when_it_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            default_path = Path(tmp_dir) / "config.yml"

            resolved = resolve_init_config_path(
                default_path=default_path,
                prompt=lambda _message: self.fail("prompt should not be called"),
                confirm_overwrite=lambda _path: self.fail(
                    "confirm should not be called"
                ),
            )

        self.assertEqual(resolved, default_path)

    def test_existing_default_prompts_for_alternate_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            default_path = Path(tmp_dir) / "config.yml"
            default_path.write_text("existing: true\n", encoding="utf-8")

            resolved = resolve_init_config_path(
                default_path=default_path,
                prompt=lambda _message: "custom.yml",
                confirm_overwrite=lambda _path: self.fail(
                    "confirm should not be called"
                ),
            )

        self.assertEqual(resolved, Path(tmp_dir) / "custom.yml")

    def test_existing_same_path_requires_overwrite_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            default_path = Path(tmp_dir) / "config.yml"
            default_path.write_text("existing: true\n", encoding="utf-8")

            resolved = resolve_init_config_path(
                default_path=default_path,
                prompt=lambda _message: "config.yml",
                confirm_overwrite=lambda path: path == default_path,
            )

        self.assertEqual(resolved, default_path)

    def test_declined_overwrite_returns_to_path_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            default_path = Path(tmp_dir) / "config.yml"
            default_path.write_text("existing: true\n", encoding="utf-8")
            answers = iter(["config.yml", "safe.yml"])

            resolved = resolve_init_config_path(
                default_path=default_path,
                prompt=lambda _message: next(answers),
                confirm_overwrite=lambda _path: False,
            )

        self.assertEqual(resolved, Path(tmp_dir) / "safe.yml")


class InitConfigCliTests(unittest.TestCase):
    """CLI dispatch tests for --init."""

    def test_init_does_not_require_repo_paths_or_config(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")

        with patch.object(sys, "argv", ["analyze_git_repo_loc", "--init"]):
            args = parse_arguments(parser)

        self.assertTrue(args.init)
        self.assertIsNone(args.repo_paths)
        self.assertIsNone(args.config)


class OutputSummaryTests(unittest.TestCase):
    """Final output summary formatting tests."""

    def test_output_summary_lists_report_data_charts_and_cache(self) -> None:
        output_root = Path("out")
        output_dir = output_root / "20260522010101"

        lines = _format_output_summary(output_dir=output_dir, output_root=output_root)

        self.assertEqual(lines[0], "Finished")
        self.assertIn(f"Report: {output_dir / 'report.html'}", lines)
        self.assertIn(f"Summary: {output_dir / 'summary.md'}", lines)
        self.assertIn(f"Run data: {output_dir}", lines)
        self.assertIn(f"Repository charts: {output_root}", lines)
        self.assertIn(f"Cache: {output_root / '.cache'}", lines)
