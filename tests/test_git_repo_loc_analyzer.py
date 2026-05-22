"""Tests for Git repository analysis helpers."""

from __future__ import annotations

import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
