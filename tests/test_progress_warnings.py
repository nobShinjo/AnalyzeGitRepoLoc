from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from analyze_git_repo_loc import utils
from analyze_git_repo_loc.git_repo_loc_analyzer import GitRepoLOCAnalyzer
from analyze_git_repo_loc.i18n import tr


class RepositoryWarningTests(unittest.TestCase):
    """Repository warning collection tests."""

    def test_missing_exclude_dir_is_collected_without_direct_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "alpha"
            repo_path.mkdir()
            stderr = StringIO()

            with patch.object(sys, "stderr", stderr):
                analyzer = GitRepoLOCAnalyzer(
                    repo_path=repo_path,
                    branch_name="main",
                    cache_dir=Path(tmp_dir) / "cache",
                    output_dir=Path(tmp_dir) / "out",
                    exclude_dirs=["node_modules"],
                    show_progress=False,
                )

        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            analyzer._warnings,
            ["excluded path does not exist: node_modules"],
        )

    def test_single_repository_returns_collected_warnings(self) -> None:
        loc_data = pd.DataFrame({"repository": ["alpha"]})
        analyzer = Mock()
        analyzer.get_commit_analysis.return_value = loc_data
        analyzer._warnings = ["excluded path does not exist: .venv"]

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "alpha"
            repo_path.mkdir()
            with patch.object(utils, "_resolve_analysis_repo_path", return_value=repo_path):
                with patch.object(utils, "_create_analyzer", return_value=analyzer):
                    _, repository_name, _, warnings = utils._analyze_single_repository(
                        index=0,
                        repo_path=repo_path,
                        branch_name="main",
                        exclude_dirs=[Path(".venv")],
                        include_subpath=None,
                        output_dir=Path(tmp_dir) / "out",
                        since=None,
                        until=None,
                        authors=None,
                        languages=None,
                        clear_cache=False,
                        show_progress=False,
                    )

        self.assertEqual(repository_name, "alpha")
        self.assertEqual(warnings, ["excluded path does not exist: .venv"])

    def test_repository_warnings_are_printed_as_summary(self) -> None:
        stderr = StringIO()

        with patch.object(sys, "stderr", stderr):
            utils._print_repository_warnings(
                [
                    "SoFiRA: excluded path does not exist: node_modules",
                    "AgvController: excluded path does not exist: .venv",
                ]
            )

        self.assertEqual(
            stderr.getvalue(),
            f"{tr('warnings.title')}\n"
            "- SoFiRA: excluded path does not exist: node_modules\n"
            "- AgvController: excluded path does not exist: .venv\n",
        )


class RepositoryProgressTests(unittest.TestCase):
    """Repository-level progress behavior tests."""

    def test_sequential_analysis_suppresses_child_progress_by_default(self) -> None:
        loc_data = pd.DataFrame({"repository": ["alpha"]})
        args = argparse.Namespace(
            output=Path("out"),
            since=None,
            until=None,
            author_name=None,
            lang=None,
            clear_cache=False,
            exclude_dirs=None,
        )
        progress = Mock()
        results: dict[int, pd.DataFrame] = {}
        warnings: list[str] = []

        with patch.object(
            utils,
            "_analyze_single_repository",
            return_value=(0, "alpha", loc_data, []),
        ) as analyze:
            utils._analyze_repositories_sequential(
                args=args,
                repo_entries=[(Path("alpha"), "main", [], None)],
                progress=progress,
                results=results,
                warnings=warnings,
            )

        self.assertFalse(analyze.call_args.kwargs["show_progress"])
        self.assertEqual(results[0].to_dict("list"), loc_data.to_dict("list"))
        progress.update.assert_called_once_with(1)
