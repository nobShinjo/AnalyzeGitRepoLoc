"""Tests for repository progress reporting and warning aggregation helpers."""

from __future__ import annotations

# pylint: disable=missing-function-docstring

import argparse
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import ANY, MagicMock, Mock, patch

import pandas as pd

from analyze_git_repo_loc import utils
from analyze_git_repo_loc.analysis.analysis_runner import _SingleRepositoryAnalysisRequest
from analyze_git_repo_loc.analysis.git_repo_loc_analyzer import (
    GitRepoLOCAnalyzer,
    GitRepoLOCAnalyzerOptions,
)
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.repo_progress import (
    REPO_EVENT_ADVANCE,
    REPO_EVENT_FINISH,
    REPO_EVENT_SCAN_ADVANCE,
    REPO_EVENT_SCAN_TOTAL,
    REPO_EVENT_TOTAL,
    REPO_PROGRESS_BAR_FORMAT,
    apply_repo_progress_event,
    format_repo_progress_description,
    truncate_repo_label,
)


class RepositoryWarningTests(unittest.TestCase):
    """Repository warning collection tests."""

    def test_utils_resolve_analysis_repo_path_forwards_update_remote(self) -> None:
        manager = Mock()
        manager.is_git_url.return_value = True
        manager.prepare_remote_repository.return_value = Path("cache/repo")

        with patch.object(utils, "_REMOTE_REPO_MANAGER", manager):
            # pylint: disable-next=protected-access
            result = utils._resolve_analysis_repo_path(
                "https://github.com/org/repo.git",
                "main",
                Path("cache"),
                update_remote=False,
            )

        self.assertEqual(result, Path("cache/repo"))
        manager.prepare_remote_repository.assert_called_once_with(
            repo_url="https://github.com/org/repo.git",
            branch_name="main",
            cache_dir=Path("cache"),
            update_remote=False,
        )

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
                    options=GitRepoLOCAnalyzerOptions(
                        exclude_dirs=["node_modules"],
                    ),
                    show_progress=False,
                )

        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            analyzer.get_warnings(),
            ["excluded path does not exist: node_modules"],
        )

    def test_single_repository_returns_collected_warnings(self) -> None:
        loc_data = pd.DataFrame({"repository": ["alpha"]})
        analyzer = Mock()
        analyzer.get_commit_analysis.return_value = loc_data
        analyzer.get_warnings.return_value = [
            "excluded path does not exist: .venv"
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "alpha"
            repo_path.mkdir()
            with patch.object(utils, "_resolve_analysis_repo_path", return_value=repo_path):
                with patch.object(utils, "_create_analyzer", return_value=analyzer):
                    (
                        _,
                        repository_name,
                        _,
                        warnings,
                        exclude_summary,
                    ) = (
                        # pylint: disable-next=protected-access
                        utils._analyze_single_repository(
                        index=0,
                        repo_path=repo_path,
                        branch_name="main",
                        exclude_dirs=[".venv"],
                        include_subpath=None,
                        exclude_template_mode="manual",
                        exclude_template_names=None,
                        exclude_template_files=None,
                        output_dir=Path(tmp_dir) / "out",
                        since=None,
                        until=None,
                        authors=None,
                        languages=None,
                        clear_cache=False,
                        show_progress=False,
                    ))

        self.assertEqual(repository_name, "alpha")
        self.assertEqual(warnings, ["excluded path does not exist: .venv"])
        self.assertEqual(exclude_summary["repository"], "alpha")

    def test_single_repository_returns_exclude_template_summary(self) -> None:
        loc_data = pd.DataFrame({"repository": ["alpha"]})
        analyzer = Mock()
        analyzer.get_commit_analysis.return_value = loc_data
        analyzer.get_warnings.return_value = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "alpha"
            repo_path.mkdir()
            (repo_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            with patch.object(utils, "_resolve_analysis_repo_path", return_value=repo_path):
                with patch.object(utils, "_create_analyzer", return_value=analyzer):
                    (
                        _,
                        repository_name,
                        _,
                        _,
                        exclude_summary,
                    ) = (
                        # pylint: disable-next=protected-access
                        utils._analyze_single_repository(
                        index=0,
                        repo_path=repo_path,
                        branch_name="main",
                        exclude_dirs=["manual-cache"],
                        include_subpath=None,
                        exclude_template_mode="auto",
                        exclude_template_names=None,
                        exclude_template_files=None,
                        output_dir=Path(tmp_dir) / "out",
                        since=None,
                        until=None,
                        authors=None,
                        languages=None,
                        clear_cache=False,
                        show_progress=False,
                    ))

        self.assertEqual(repository_name, "alpha")
        self.assertEqual(exclude_summary["repository"], "alpha")
        self.assertEqual(exclude_summary["mode"], "auto")
        self.assertIn("Python Project", cast(list[str], exclude_summary["templates"]))
        self.assertIn(".venv", cast(list[str], exclude_summary["template_paths"]))
        self.assertIn(
            "manual-cache",
            cast(list[str], exclude_summary["excluded_paths"]),
        )

    def test_single_repository_accepts_request_object(self) -> None:
        loc_data = pd.DataFrame({"repository": ["alpha"]})
        analyzer = Mock()
        analyzer.get_commit_analysis.return_value = loc_data
        analyzer.get_warnings.return_value = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "alpha"
            repo_path.mkdir()
            request = _SingleRepositoryAnalysisRequest(
                index=0,
                repo_path=repo_path,
                branch_name="main",
                exclude_dirs=None,
                include_subpath=None,
                exclude_template_mode="auto",
                exclude_template_names=None,
                exclude_template_files=None,
                output_dir=Path(tmp_dir) / "out",
                since=None,
                until=None,
                authors=None,
                languages=None,
                clear_cache=False,
                show_progress=False,
            )
            with patch.object(utils, "_resolve_analysis_repo_path", return_value=repo_path):
                with patch.object(utils, "_create_analyzer", return_value=analyzer):
                    (
                        index,
                        repository_name,
                        returned_loc_data,
                        warnings,
                        exclude_summary,
                    ) = (
                        # pylint: disable-next=protected-access
                        cast(Any, utils._analyze_single_repository)(request)
                    )

        self.assertEqual(index, 0)
        self.assertEqual(repository_name, "alpha")
        self.assertEqual(returned_loc_data.to_dict("list"), loc_data.to_dict("list"))
        self.assertEqual(warnings, [])
        self.assertEqual(exclude_summary["repository"], "alpha")

    def test_template_exclude_dir_does_not_emit_missing_path_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "alpha"
            repo_path.mkdir()
            (repo_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            analyzer = GitRepoLOCAnalyzer(
                repo_path=repo_path,
                branch_name="main",
                cache_dir=Path(tmp_dir) / "cache",
                output_dir=Path(tmp_dir) / "out",
                options=GitRepoLOCAnalyzerOptions(
                    exclude_dirs=[".venv"],
                    exclude_warning_dirs=[],
                ),
                show_progress=False,
            )

        self.assertEqual(analyzer.get_warnings(), [])

    def test_missing_exclude_path_warnings_are_omitted_from_summary(self) -> None:
        stderr = StringIO()

        with patch.object(sys, "stderr", stderr):
            # pylint: disable-next=protected-access
            utils._print_repository_warnings(
                [
                    "SoFiRA: excluded path does not exist: node_modules",
                    "AgvController: excluded path does not exist: .venv",
                ]
            )

        self.assertEqual(stderr.getvalue(), "")

    def test_non_exclude_path_warnings_are_printed_as_summary(self) -> None:
        stderr = StringIO()

        with patch.object(sys, "stderr", stderr):
            # pylint: disable-next=protected-access
            utils._print_repository_warnings(["SoFiRA: unexpected warning"])

        self.assertEqual(
            stderr.getvalue(),
            f"{tr('warnings.title')}\n- SoFiRA: unexpected warning\n",
        )

    def test_repository_exclude_summary_is_printed_after_progress(self) -> None:
        stdout = StringIO()

        with patch.object(sys, "stdout", stdout):
            # pylint: disable-next=protected-access
            utils._print_repository_exclude_summaries(
                [
                    {
                        "repository": "SoFiRA",
                        "mode": "auto",
                        "templates": ["Python Project", "Node.js Project"],
                        "excluded_paths": ["node_modules", ".venv"],
                        "template_paths": ["node_modules", ".venv"],
                    },
                    {
                        "repository": "ci-scripts",
                        "mode": "auto",
                        "templates": [],
                        "excluded_paths": ["node_modules", ".venv"],
                        "template_paths": [],
                    },
                ]
            )

        self.assertIn(tr("exclude.summary.title"), stdout.getvalue())
        self.assertIn(
            f"- ci-scripts                      : {tr('exclude.summary.none')}",
            stdout.getvalue(),
        )
        self.assertIn(
            "- SoFiRA                          : Python Project, Node.js Project",
            stdout.getvalue(),
        )
        self.assertNotIn(tr("exclude.summary.paths"), stdout.getvalue())
        self.assertNotIn("node_modules", stdout.getvalue())


class RepositoryProgressTests(unittest.TestCase):
    """Repository-level progress behavior tests."""

    def test_repo_child_progress_starts_without_fake_total_and_uses_commit_unit(
        self,
    ) -> None:
        progress = Mock()
        progress.pos = 0

        with patch.object(utils, "tqdm") as tqdm_mock:
            # pylint: disable-next=protected-access
            utils._build_repo_progress_bars(
                [(Path("alpha"), "main", [], None)],
                progress=progress,
                label_width=32,
            )

        tqdm_mock.assert_called_once_with(
            total=None,
            desc=format_repo_progress_description(
                "alpha", tr("progress.repo.status.queued")
            ),
            position=1,
            leave=True,
            unit="commit",
            bar_format=REPO_PROGRESS_BAR_FORMAT,
        )

    def test_repo_child_progress_truncates_long_labels_with_ascii_ellipsis(
        self,
    ) -> None:
        long_name = "alpha-service-with-a-very-long-repository-name"
        label = truncate_repo_label(long_name, 32)

        self.assertEqual(label, "alpha-service-with-a-very-lon...")
        self.assertEqual(len(label), 32)

    def test_repo_child_progress_descriptions_keep_fixed_width(self) -> None:
        descriptions = [
            format_repo_progress_description("alpha", status)
            for status in (
                tr("progress.repo.status.queued"),
                tr("progress.repo.status.getting_commits"),
                tr("progress.repo.status.analyzing_commits"),
                tr("progress.repo.status.done"),
            )
        ]

        self.assertEqual(len(set(map(len, descriptions))), 1)
        self.assertTrue(descriptions[0].startswith("  Repo: "))

    def test_repo_child_progress_count_format_uses_fixed_width(self) -> None:
        self.assertIn(
            "{n_fmt:>5}/{total_fmt:>5}",
            REPO_PROGRESS_BAR_FORMAT,
        )

    def test_repo_child_progress_tracks_commit_scan_before_analysis(self) -> None:
        progress_bar = Mock()
        progress_bar.n = 0
        progress_bar.total = None

        self.assertTrue(
            apply_repo_progress_event(
                kind=REPO_EVENT_SCAN_ADVANCE,
                bar=progress_bar,
                label="alpha",
                value=7,
            )
        )

        self.assertIsNone(progress_bar.total)
        progress_bar.update.assert_called_once_with(7)

    def test_repo_child_progress_uses_commit_scan_total(self) -> None:
        progress_bar = Mock()
        progress_bar.n = 0
        progress_bar.total = None

        self.assertTrue(
            apply_repo_progress_event(
                kind=REPO_EVENT_SCAN_TOTAL,
                bar=progress_bar,
                label="alpha",
                value=300,
            )
        )

        self.assertEqual(progress_bar.total, 300)
        self.assertEqual(progress_bar.n, 0)
        progress_bar.set_description_str.assert_called_once_with(
            format_repo_progress_description(
                "alpha", tr("progress.repo.status.getting_commits")
            )
        )
        progress_bar.refresh.assert_called_once()

    def test_repo_child_progress_switches_to_analysis_total(self) -> None:
        progress_bar = Mock()
        progress_bar.n = 21
        progress_bar.total = None

        self.assertTrue(
            apply_repo_progress_event(
                kind=REPO_EVENT_TOTAL,
                bar=progress_bar,
                label="alpha",
                value=12,
            )
        )

        self.assertEqual(progress_bar.total, 12)
        self.assertEqual(progress_bar.n, 0)
        progress_bar.set_description_str.assert_called_once_with(
            format_repo_progress_description(
                "alpha", tr("progress.repo.status.analyzing_commits")
            )
        )
        progress_bar.refresh.assert_called_once()

    def test_repo_child_progress_uses_commit_total_and_advance_events(self) -> None:
        progress_bar = Mock()
        progress_bar.n = 0
        progress_bar.total = None

        self.assertTrue(
            apply_repo_progress_event(
                kind=REPO_EVENT_TOTAL,
                bar=progress_bar,
                label="alpha",
                value=12,
            )
        )
        apply_repo_progress_event(
            kind=REPO_EVENT_ADVANCE,
            bar=progress_bar,
            label="alpha",
            value=3,
        )

        self.assertEqual(progress_bar.total, 12)
        self.assertEqual(progress_bar.n, 0)
        progress_bar.update.assert_called_once_with(3)

    def test_repo_child_progress_shows_zero_target_commits_on_finish(self) -> None:
        progress_bar = Mock()
        progress_bar.n = 0
        progress_bar.total = 0

        self.assertTrue(
            apply_repo_progress_event(
                kind=REPO_EVENT_FINISH,
                bar=progress_bar,
                label="alpha",
                value=0,
            )
        )

        progress_bar.update.assert_not_called()
        progress_bar.set_description_str.assert_called_once_with(
            format_repo_progress_description(
                "alpha", tr("progress.repo.status.done")
            )
        )

    def test_repo_child_progress_finishes_at_total(self) -> None:
        progress_bar = Mock()
        progress_bar.n = 7
        progress_bar.total = 12

        self.assertTrue(
            apply_repo_progress_event(
                kind=REPO_EVENT_FINISH,
                bar=progress_bar,
                label="alpha",
                value=0,
            )
        )

        progress_bar.update.assert_called_once_with(5)
        progress_bar.set_description_str.assert_called_once_with(
            format_repo_progress_description(
                "alpha", tr("progress.repo.status.done")
            )
        )

    def test_sequential_analysis_emits_child_progress_events_when_queue_is_provided(
        self,
    ) -> None:
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
        progress_queue = Mock()
        results: dict[int, pd.DataFrame] = {}
        warnings: list[str] = []

        with patch.object(
            utils,
            "_analyze_single_repository",
            return_value=(0, "alpha", loc_data, [], {}),
        ) as analyze:
            # pylint: disable-next=protected-access
            utils._analyze_repositories_sequential(
                args=args,
                repo_entries=[(Path("alpha"), "main", [], None)],
                progress=progress,
                progress_queue=progress_queue,
                results=results,
                warnings=warnings,
                exclude_summaries=[],
            )

        request = analyze.call_args.args[0]
        self.assertFalse(request.show_progress)
        self.assertIs(request.progress_queue, progress_queue)
        self.assertEqual(results[0].to_dict("list"), loc_data.to_dict("list"))
        progress.update.assert_called_once_with(1)

    def test_sequential_analysis_adapter_accepts_error_handler(self) -> None:
        args = argparse.Namespace()
        progress = Mock()
        error_handler = Mock()

        with patch(
            "analyze_git_repo_loc.analysis.analysis_runner._analyze_repositories_sequential"
        ) as impl:
            # pylint: disable-next=protected-access
            utils._analyze_repositories_sequential(
                args=args,
                repo_entries=[],
                progress=progress,
                results={},
                warnings=[],
                exclude_summaries=[],
                error_handler=error_handler,
            )

        self.assertIs(impl.call_args.kwargs["error_handler"], error_handler)

    def test_parallel_analysis_adapter_accepts_error_handler(self) -> None:
        args = argparse.Namespace()
        progress = Mock()
        error_handler = Mock()

        with patch(
            "analyze_git_repo_loc.analysis.analysis_runner._analyze_repositories_parallel"
        ) as impl:
            # pylint: disable-next=protected-access
            utils._analyze_repositories_parallel(
                args=args,
                repo_entries=[],
                worker_count=2,
                progress=progress,
                results={},
                warnings=[],
                exclude_summaries=[],
                error_handler=error_handler,
            )

        self.assertIs(impl.call_args.kwargs["error_handler"], error_handler)

    def test_analyze_git_repositories_starts_repo_child_progress_bars(self) -> None:
        loc_data = pd.DataFrame({"repository": ["alpha"]})
        args = argparse.Namespace(
            repo_paths=[(Path("alpha"), "main", [], None)],
            output=Path("out"),
            since=None,
            until=None,
            author_name=None,
            lang=None,
            clear_cache=False,
            exclude_dirs=None,
            workers=1,
        )
        parent_progress = MagicMock()
        parent_progress.pos = 0
        progress_context = MagicMock()
        progress_context.__enter__.return_value = parent_progress
        manager = Mock()
        progress_queue = Mock()
        manager.Queue.return_value = progress_queue
        repo_bars = {0: Mock()}
        repo_labels = {0: "alpha"}
        stop_event = Mock()
        listener_thread = Mock()

        def analyze_side_effect(**kwargs: object) -> None:
            kwargs["results"][0] = loc_data  # type: ignore[index]

        with patch.object(utils, "tqdm", return_value=progress_context):
            with patch.object(utils, "Manager", return_value=manager):
                with patch.object(
                    utils,
                    "_build_repo_progress_bars",
                    return_value=(repo_bars, repo_labels),
                ) as build_bars:
                    with patch.object(
                        utils,
                        "_start_repo_progress_listener",
                        return_value=(stop_event, listener_thread),
                    ) as start_listener:
                        with patch.object(
                            utils,
                            "_cleanup_repo_progress_listener",
                        ) as cleanup_listener:
                            with patch.object(
                                utils,
                                "_analyze_repositories_sequential",
                                side_effect=analyze_side_effect,
                            ) as analyze:
                                result = utils.analyze_git_repositories(args)

        self.assertEqual(result[0].to_dict("list"), loc_data.to_dict("list"))
        build_bars.assert_called_once_with(
            args.repo_paths,
            progress=parent_progress,
            label_width=ANY,
        )
        start_listener.assert_called_once_with(
            progress_queue=progress_queue,
            repo_bars=repo_bars,
            repo_labels=repo_labels,
        )
        self.assertIs(analyze.call_args.kwargs["progress_queue"], progress_queue)
        cleanup_listener.assert_called_once_with(
            stop_event=stop_event,
            listener_thread=listener_thread,
            repo_bars=repo_bars,
            manager=manager,
            progress_queue=progress_queue,
        )
