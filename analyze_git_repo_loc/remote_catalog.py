"""Compatibility wrapper for remote catalog helpers.

Description:
    Aliases the historical module path to the implementation in the `remote`
    package so existing imports and patches keep working.
"""

import sys

from analyze_git_repo_loc.remote import remote_catalog as _impl

sys.modules[__name__] = _impl
