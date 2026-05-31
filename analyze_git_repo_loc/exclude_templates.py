"""Compatibility wrapper for exclude-template helpers.

Description:
    Aliases the historical module path to the implementation in the
    `analysis` package so existing imports keep working.
"""

import sys

from analyze_git_repo_loc.analysis import exclude_templates as _impl

sys.modules[__name__] = _impl
