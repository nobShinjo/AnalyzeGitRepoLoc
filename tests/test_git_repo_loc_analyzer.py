"""Tests for Git repository analysis helpers."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from analyze_git_repo_loc.git_repo_loc_analyzer import GitRepoLOCAnalyzer


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
            "analyze_git_repo_loc.git_repo_loc_analyzer.tqdm",
            side_effect=lambda iterable, **_kwargs: iterable,
        ):
            result = analyzer._get_commits(repository, progress_callback=callback)

        self.assertEqual(result, commits)
        callback.assert_any_call("scan_advance", 1)
        self.assertEqual(callback.call_count, 3)


if __name__ == "__main__":
    unittest.main()
