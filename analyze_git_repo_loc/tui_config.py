"""Compatibility wrapper for interactive TUI config helpers.

Description:
    Aliases the historical module path to the implementation in the
    `interactive` package so existing imports keep working.
"""

import sys

from analyze_git_repo_loc.interactive import tui_config as _impl

sys.modules[__name__] = _impl
