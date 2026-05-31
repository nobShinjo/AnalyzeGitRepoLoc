"""Compatibility wrapper for Git repository LOC analyzer.

Description:
    Aliases the historical module path to the implementation in the
    `analysis` package so existing imports and patches keep working.
"""

import sys

from analyze_git_repo_loc.analysis import git_repo_loc_analyzer as _impl

sys.modules[__name__] = _impl
