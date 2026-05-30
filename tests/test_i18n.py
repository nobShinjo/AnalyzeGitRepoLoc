"""Tests for locale-based user-facing translations."""

from __future__ import annotations

import unittest
import tempfile
from argparse import ArgumentParser
from pathlib import Path
from unittest.mock import patch

from analyze_git_repo_loc.i18n import resolve_language, set_language_override, tr
from analyze_git_repo_loc.init_wizard import _InitWizardController
from analyze_git_repo_loc.utils import parse_arguments


class I18nTests(unittest.TestCase):
    """Locale detection and translation lookup tests."""

    def tearDown(self) -> None:
        set_language_override(None)

    def test_resolves_japanese_locales_to_japanese(self) -> None:
        self.assertEqual(resolve_language("ja_JP"), "jp")
        self.assertEqual(resolve_language("Japanese_Japan.932"), "jp")

    def test_resolves_unknown_or_english_locales_to_english(self) -> None:
        self.assertEqual(resolve_language("en_US"), "en")
        self.assertEqual(resolve_language("C"), "en")
        self.assertEqual(resolve_language(None), "en")

    def test_translates_with_format_arguments(self) -> None:
        self.assertEqual(
            tr("init.created_config", language="en", path="config.yml"),
            "Created config: config.yml",
        )
        self.assertEqual(
            tr("init.created_config", language="jp", path="config.yml"),
            "設定ファイルを作成しました: config.yml",
        )

    def test_translates_run_progress_messages(self) -> None:
        self.assertEqual(
            tr("run.section.forming_dataframe", language="en"),
            "Forming dataframe type data.",
        )
        self.assertEqual(
            tr("run.section.forming_dataframe", language="jp"),
            "DataFrame 形式のデータを整形します。",
        )
        self.assertEqual(
            tr("progress.repo.status.getting_commits", language="jp"),
            "commit 取得中",
        )
        self.assertEqual(
            tr("output.report", language="jp", path="out/report.html"),
            "レポート: out/report.html",
        )

    def test_missing_key_and_locale_fall_back_safely(self) -> None:
        self.assertEqual(tr("missing.key", language="jp"), "missing.key")
        self.assertEqual(tr("cli.description", language="fr"), tr("cli.description"))

    def test_cli_help_uses_japanese_os_locale(self) -> None:
        parser = ArgumentParser(prog="analyze_git_repo_loc")

        with (
            patch("locale.getlocale", return_value=("ja_JP", "UTF-8")),
            patch("sys.argv", ["analyze_git_repo_loc", "init"]),
        ):
            args = parse_arguments(parser)

        self.assertEqual(args.command, "init")
        self.assertEqual(parser.description, "Git リポジトリを解析し、コード LOC を可視化します。")

    def test_display_language_option_overrides_japanese_os_locale(self) -> None:
        parser = ArgumentParser(
            prog="analyze_git_repo_loc",
            description="Git リポジトリを解析し、コード LOC を可視化します。",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text("repositories:\n- path: .\n", encoding="utf-8")
            with (
                patch("locale.getlocale", return_value=("ja_JP", "UTF-8")),
                patch(
                    "sys.argv",
                    [
                        "analyze_git_repo_loc",
                        "run",
                        "--display-language",
                        "en",
                        "--config",
                        str(config_path),
                    ],
                ),
            ):
                args = parse_arguments(parser)

        self.assertEqual(args.display_language, "en")
        self.assertEqual(parser.description, "Analyze Git repositories and visualize code LOC.")
        self.assertEqual(tr("run.section.generate_html_report"), "Generate HTML report.")

    def test_short_display_language_option_overrides_japanese_os_locale(self) -> None:
        parser = ArgumentParser(prog="analyze_git_repo_loc")

        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text("repositories:\n- path: .\n", encoding="utf-8")
            with (
                patch("locale.getlocale", return_value=("ja_JP", "UTF-8")),
                patch(
                    "sys.argv",
                    [
                        "analyze_git_repo_loc",
                        "run",
                        "-L",
                        "en",
                        "--config",
                        str(config_path),
                    ],
                ),
            ):
                args = parse_arguments(parser)

        self.assertEqual(args.display_language, "en")
        self.assertEqual(parser.description, "Analyze Git repositories and visualize code LOC.")

    def test_global_display_language_option_overrides_japanese_os_locale(self) -> None:
        parser = ArgumentParser(prog="analyze_git_repo_loc")

        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text("repositories:\n- path: .\n", encoding="utf-8")
            with (
                patch("locale.getlocale", return_value=("ja_JP", "UTF-8")),
                patch(
                    "sys.argv",
                    [
                        "analyze_git_repo_loc",
                        "--display-language",
                        "en",
                        "run",
                        "--config",
                        str(config_path),
                    ],
                ),
            ):
                args = parse_arguments(parser)

        self.assertEqual(args.display_language, "en")
        self.assertEqual(parser.description, "Analyze Git repositories and visualize code LOC.")

    def test_init_wizard_uses_japanese_os_locale(self) -> None:
        controller = _InitWizardController(Path("missing.yml"))

        with patch("locale.getlocale", return_value=("ja_JP", "UTF-8")):
            rendered = controller.render()

        self.assertIn("AnalyzeGitRepoLoc 初期設定ウィザード", rendered)


if __name__ == "__main__":
    unittest.main()
