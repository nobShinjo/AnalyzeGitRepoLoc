"""Compatibility wrapper for chart builder helpers.

Description:
    Aliases the historical module path to the implementation in the
    `reporting` package so existing imports keep working.
"""

import sys

from analyze_git_repo_loc.reporting import chart_builder as _impl

sys.modules[__name__] = _impl
