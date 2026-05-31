"""Compatibility wrapper for YAML config helpers.

Description:
    Aliases the historical module path to the implementation in the
    `config` package so existing imports keep working.
"""

import sys

from analyze_git_repo_loc.config import yaml_config as _impl

sys.modules[__name__] = _impl
