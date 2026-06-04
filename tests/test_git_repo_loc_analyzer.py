"""Tests for Git repository analysis helpers."""

from __future__ import annotations

# pylint: disable=missing-function-docstring

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from analyze_git_repo_loc.analysis.git_repo_loc_analyzer import GitRepoLOCAnalyzer


class RepositoryDisplayNameTests(unittest.TestCase):
    """Repository display-name tests."""

    def test_display_name_uses_repo_ref_instead_of_hashed_cache_path(self) -> None:
        cache_path = Path("out/.cache/remote-repos/AnalyzeGitRepoLoc-5eea8ac49b47")
        repo_ref = "https://github.com/example/AnalyzeGitRepoLoc.git"

        display_name = GitRepoLOCAnalyzer.get_repository_display_name(
            cache_path,
            repo_ref,
        )

        self.assertEqual(display_name, "AnalyzeGitRepoLoc")

    def test_display_name_falls_back_to_local_path_name(self) -> None:
        display_name = GitRepoLOCAnalyzer.get_repository_display_name(
            Path("C:/repos/local-project"),
            None,
        )

        self.assertEqual(display_name, "local-project")


class CommitProgressTests(unittest.TestCase):
    """Commit progress callback tests."""

    def test_get_commits_emits_scan_total_when_available(self) -> None:
        commits = [object(), object()]
        repository = Mock()
        repository.traverse_commits.return_value = iter(commits)
        callback = Mock()
        analyzer = GitRepoLOCAnalyzer(
            repo_path=Path("alpha"),
            branch_name="main",
            cache_dir=Path("cache"),
            output_dir=Path("out"),
            show_progress=False,
        )

        with patch.object(analyzer, "_count_commits_for_scan", return_value=2):
            with patch(
                "analyze_git_repo_loc.analysis.git_repo_loc_analyzer.tqdm",
                side_effect=lambda iterable, **_kwargs: iterable,
            ) as tqdm_mock:
                result = analyzer._get_commits(repository, progress_callback=callback)

        self.assertEqual(result, commits)
        callback.assert_any_call("scan_total", 2)
        tqdm_mock.assert_called_once()
        self.assertEqual(tqdm_mock.call_args.kwargs["total"], 2)

    def test_get_commits_emits_scan_progress(self) -> None:
        commits = [object(), object(), object()]
        repository = Mock()
        repository.traverse_commits.return_value = iter(commits)
        callback = Mock()
        analyzer = GitRepoLOCAnalyzer(
            repo_path=Path("alpha"),
            branch_name="main",
            cache_dir=Path("cache"),
            output_dir=Path("out"),
            show_progress=False,
        )

        with patch(
            "analyze_git_repo_loc.analysis.git_repo_loc_analyzer.tqdm",
            side_effect=lambda iterable, **_kwargs: iterable,
        ):
            result = analyzer._get_commits(repository, progress_callback=callback)

        self.assertEqual(result, commits)
        callback.assert_any_call("scan_advance", 1)
        self.assertEqual(callback.call_count, 3)

    def test_analysis_progress_is_emitted_before_each_commit_is_processed(self) -> None:
        class Commit:
            def __init__(self, commit_hash: str) -> None:
                self.hash = commit_hash

        commits = [Commit("a"), Commit("b")]
        events: list[tuple[str, int]] = []
        analyzer = GitRepoLOCAnalyzer(
            repo_path=Path("alpha"),
            branch_name="main",
            cache_dir=Path("cache"),
            output_dir=Path("out"),
            show_progress=False,
        )

        def progress_callback(kind: str, value: int) -> None:
            events.append((kind, value))

        def append_rows(commit: Commit, _repository_name, _cache_lookup, rows) -> bool:
            self.assertEqual(events[-1], ("advance", 1))
            rows.append(
                {
                    "Datetime": "2026-05-27T00:00:00Z",
                    "Repository": "alpha",
                    "Branch": "main",
                    "Commit_hash": commit.hash,
                    "Author": "Nob",
                    "Language": "Python",
                    "NLOC_Added": 1,
                    "NLOC_Deleted": 0,
                    "NLOC": 1,
                }
            )
            return False

        with patch.object(analyzer, "_build_repository", return_value=object()):
            with patch.object(analyzer, "_get_commits", return_value=commits):
                with patch.object(
                    analyzer,
                    "_prepare_cache_state",
                    return_value=(commits, None, False),
                ):
                    with patch.object(
                        analyzer,
                        "_append_commit_rows",
                        side_effect=append_rows,
                    ):
                        with patch(
                            "analyze_git_repo_loc.analysis.git_repo_loc_analyzer.tqdm",
                            side_effect=lambda iterable, **_kwargs: iterable,
                        ):
                            analyzer.get_commit_analysis(progress_callback)

        self.assertEqual(events, [("total", 2), ("advance", 1), ("advance", 1)])

    def test_analysis_progress_tracker_emits_each_commit(self) -> None:
        events: list[tuple[str, int]] = []

        record, flush = GitRepoLOCAnalyzer._create_progress_tracker(
            lambda kind, value: events.append((kind, value)),
            total_commits=250,
        )
        for _ in range(5):
            record(1)
        flush()

        self.assertEqual(
            events,
            [
                ("total", 250),
                ("advance", 1),
                ("advance", 1),
                ("advance", 1),
                ("advance", 1),
                ("advance", 1),
            ],
        )


if __name__ == "__main__":
    unittest.main()
