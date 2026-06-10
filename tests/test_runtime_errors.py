"""Tests for runtime error handling."""

from __future__ import annotations

# pylint: disable=missing-function-docstring

import errno
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from analyze_git_repo_loc import __main__ as cli_main
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.utils import handle_exception


class RuntimeErrorHandlingTests(unittest.TestCase):
    """Runtime error handling tests."""

    def test_handle_exception_prints_disk_space_message_without_stack_trace(
        self,
    ) -> None:
        stderr = StringIO()
        error = OSError(errno.ENOSPC, "No space left on device")

        with patch.object(sys, "stderr", stderr):
            with self.assertRaises(SystemExit) as ctx:
                handle_exception(error)

        self.assertEqual(ctx.exception.code, 1)
        output = stderr.getvalue()
        self.assertIn(tr("error.disk_space"), output)
        self.assertNotIn(tr("error.stack_trace"), output)

    def test_generate_charts_handles_disk_space_error(self) -> None:
        error = OSError(errno.ENOSPC, "No space left on device")
        data = pd.DataFrame({"Date": [], "Language": [], "NLOC": []})

        with patch.object(cli_main, "generate_trend_chart", side_effect=error):
            with patch.object(cli_main, "handle_exception") as error_handler:
                cli_main._generate_charts(
                    output_root=Path("out"),
                    output_dir=Path("out") / "run",
                    time_interval="monthly",
                    suppress_plot_show=True,
                    language_analysis=data,
                    author_analysis=data,
                    repository_trend_analysis=data,
                )

        error_handler.assert_called_once_with(error)

    def test_main_handles_disk_space_error_from_analysis(self) -> None:
        error = OSError(errno.ENOSPC, "No space left on device")
        args = Mock(command="run")

        with patch.object(cli_main, "parse_arguments", return_value=args):
            with patch.object(cli_main, "_apply_interactive_repository_selection"):
                with patch.object(cli_main, "_print_start"):
                    with patch.object(
                        cli_main,
                        "analyze_git_repositories",
                        side_effect=error,
                    ):
                        with patch.object(cli_main, "handle_exception") as handler:
                            cli_main.main()

        handler.assert_called_once_with(error)
