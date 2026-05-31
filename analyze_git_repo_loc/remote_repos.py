"""Compatibility wrapper for remote repository cache helpers.

Description:
    Aliases the historical module path to the implementation in the `remote`
    package so existing imports keep working.
"""

import sys

from analyze_git_repo_loc.remote import remote_repos as _impl

sys.modules[__name__] = _impl
