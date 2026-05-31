"""Compatibility wrapper for init wizard helpers.

Description:
    Aliases the historical module path to the implementation in the
    `config` package so existing imports and patches keep working.
"""

import sys

from analyze_git_repo_loc.config import init_wizard as _impl

sys.modules[__name__] = _impl
