"""Shared runtime error helpers.

Description:
    Defines user-facing runtime exceptions and detection helpers for common
    operating-system failures that should not be reported as generic crashes.
Classes:
    DiskSpaceError:
        Raised when an operation cannot continue because disk space is exhausted.
Functions:
    is_disk_space_error:
        Return whether an exception indicates insufficient disk space.
"""

from __future__ import annotations

import errno


class DiskSpaceError(RuntimeError):
    """User-facing insufficient disk space error."""


def is_disk_space_error(ex: BaseException) -> bool:
    """Return whether an exception indicates insufficient disk space."""
    if isinstance(ex, DiskSpaceError):
        return True
    if isinstance(ex, OSError):
        if ex.errno == errno.ENOSPC or getattr(ex, "winerror", None) == 112:
            return True

    text = str(ex).lower()
    return any(
        marker in text
        for marker in (
            "no space left on device",
            "not enough space on the disk",
            "there is not enough space",
            "disk full",
            "enospc",
        )
    )
