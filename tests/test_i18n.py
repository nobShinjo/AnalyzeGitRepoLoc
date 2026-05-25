"""Tests for locale-based user-facing translations."""

from __future__ import annotations

import unittest
from argparse import ArgumentParser
from pathlib import Path
from unittest.mock import patch

from analyze_git_repo_loc.i18n import resolve_language, tr
from analyze_git_repo_loc.init_wizard import _InitWizardController
from analyze_git_repo_loc.utils import parse_arguments


class I18nTests(unittest.TestCase):
    """Locale detection and translation lookup tests."""

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

    def test_init_wizard_uses_japanese_os_locale(self) -> None:
        controller = _InitWizardController(Path("missing.yml"))

        with patch("locale.getlocale", return_value=("ja_JP", "UTF-8")):
            rendered = controller.render()

        self.assertIn("AnalyzeGitRepoLoc 初期設定ウィザード", rendered)


if __name__ == "__main__":
    unittest.main()
