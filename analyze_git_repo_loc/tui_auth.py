"""Compatibility wrapper for interactive TUI auth helpers.

Description:
    Aliases the historical module path to the implementation in the
    `interactive` package so existing imports and patches keep working.
"""

import sys

from analyze_git_repo_loc.interactive import tui_auth as _impl

sys.modules[__name__] = _impl
