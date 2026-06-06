"""Tests for terminal-independent repository selector state behavior."""

from __future__ import annotations

# pylint: disable=missing-function-docstring

import sys
import types
import unittest
from collections.abc import Callable
from typing import Any, cast
from unittest.mock import patch

from analyze_git_repo_loc.interactive.tui_selector import (
    RepositorySelectorState,
    SELECTOR_PANE_GAP_WIDTH,
    SELECTOR_VERTICAL_SEPARATOR_CHAR,
    TuiSelectionCancelled,
    calculate_selector_pane_widths,
    choose_selector_layout_orientation,
    run_repository_selector,
)
from analyze_git_repo_loc.remote.remote_catalog import (
    RemoteCatalogError,
    RemoteRepositoryRef,
)


class RepositorySelectorStateTests(unittest.TestCase):
    """Terminal-independent selector behavior tests."""

    def test_search_and_toggle_visible_selection(self) -> None:
        refs = [
            RemoteRepositoryRef(
                "github",
                "alpha",
                "org/alpha",
                "https://a.git",
                "",
                "",
                "main",
            ),
            RemoteRepositoryRef(
                "gitlab",
                "beta",
                "team/beta",
                "https://b.git",
                "",
                "",
                "dev",
            ),
        ]
        state = RepositorySelectorState(refs)

        state.set_query("beta")
        state.toggle_current()

        self.assertEqual(state.visible_refs, [refs[1]])
        self.assertEqual(state.selected_refs, [refs[1]])

    def test_cancel_marks_state_cancelled(self) -> None:
        state = RepositorySelectorState(
            [
                RemoteRepositoryRef(
                    "github",
                    "alpha",
                    "org/alpha",
                    "https://a.git",
                    "",
                    "",
                    "main",
                )
            ]
        )

        state.cancel()

        self.assertTrue(state.cancelled)

    def test_tab_request_activates_branch_pane(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://a.git",
            "",
            "",
            "main",
        )
        state = RepositorySelectorState([ref])

        state.toggle_current()
        state.request_branch_selection()

        self.assertEqual(state.active_pane, "branches")
        self.assertFalse(state.confirmed)
        self.assertFalse(state.branch_selection_requested)
        self.assertEqual(state.selected_refs, [ref])

    def test_pane_switching_keeps_independent_cursors(self) -> None:
        refs = [
            RemoteRepositoryRef(
                "github",
                "alpha",
                "org/alpha",
                "https://a.git",
                "",
                "",
                "main",
            ),
            RemoteRepositoryRef(
                "github",
                "beta",
                "org/beta",
                "https://b.git",
                "",
                "",
                "main",
            ),
        ]
        state = RepositorySelectorState(
            refs,
            branch_loader=lambda _ref: ["main", "dev"],
        )

        state.move_down()
        state.activate_branch_pane()
        state.move_down()
        state.activate_repository_pane()

        self.assertEqual(state.active_pane, "repositories")
        self.assertEqual(state.cursor, 1)
        state.activate_branch_pane()
        self.assertEqual(state.branch_cursor, 1)

    def test_repo_and_branch_search_follow_active_pane(self) -> None:
        refs = [
            RemoteRepositoryRef(
                "github",
                "alpha",
                "org/alpha",
                "https://a.git",
                "",
                "",
                "main",
            ),
            RemoteRepositoryRef(
                "gitlab",
                "beta",
                "team/beta",
                "https://b.git",
                "",
                "",
                "main",
            ),
        ]
        state = RepositorySelectorState(
            refs,
            branch_loader=lambda _ref: ["main", "release"],
        )

        state.set_query("beta")
        self.assertEqual(state.visible_refs, [refs[1]])

        state.activate_branch_pane()
        state.set_query("rel")
        self.assertEqual(state.visible_branches, ["release"])

    def test_space_selects_branch_without_selecting_repo(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://a.git",
            "",
            "",
            "main",
        )
        state = RepositorySelectorState(
            [ref],
            branch_loader=lambda _ref: ["main", "dev"],
        )

        state.activate_branch_pane()
        state.move_down()
        state.toggle_current()

        self.assertEqual(state.selected_refs, [])
        self.assertEqual(state.selected_branches, {"org/alpha": "dev"})
        self.assertEqual(state.selected_branch_for(ref), "dev")

    def test_branch_fetch_failure_falls_back_to_default_branch(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://a.git",
            "",
            "",
            "develop",
        )

        def fail(_: RemoteRepositoryRef) -> list[str]:
            raise RemoteCatalogError("boom")

        state = RepositorySelectorState([ref], branch_loader=fail)

        state.activate_branch_pane()

        self.assertEqual(state.visible_branches, ["develop"])
        self.assertEqual(
            state.branch_status_for(ref),
            "Failed to load branches; using default branch",
        )

    def test_repo_and_branch_panes_render_separately(self) -> None:
        refs = [
            RemoteRepositoryRef(
                "github",
                "alpha",
                "org/alpha",
                "https://a.git",
                "",
                "",
                "main",
            ),
            RemoteRepositoryRef(
                "github",
                "beta",
                "org/beta",
                "https://b.git",
                "",
                "",
                "develop",
            ),
        ]
        state = RepositorySelectorState(
            refs,
            branch_loader=lambda _ref: ["main", "feature/tui"],
        )

        state.toggle_current()
        state.activate_branch_pane()
        state.move_down()
        state.toggle_current()

        repo_pane = state.render_repositories(height=8)
        branch_pane = state.render_branches(height=8)

        self.assertIn("Repositories", repo_pane)
        self.assertIn("[x] github org/alpha (feature/tui)", repo_pane)
        self.assertNotIn("Branches: org/alpha", repo_pane)
        self.assertIn("Branches: org/alpha", branch_pane)
        self.assertIn("2 branches", branch_pane)
        self.assertIn("[x] feature/tui", branch_pane)
        self.assertNotIn("github org/beta", branch_pane)

    def test_selector_layout_orientation_uses_horizontal_when_wide(self) -> None:
        self.assertEqual(choose_selector_layout_orientation(120), "horizontal")
        self.assertEqual(choose_selector_layout_orientation(99), "vertical")

    def test_selector_vertical_separator_uses_stable_full_height_line(self) -> None:
        self.assertEqual(SELECTOR_VERTICAL_SEPARATOR_CHAR, "│")
        self.assertEqual(SELECTOR_PANE_GAP_WIDTH, 1)

    def test_selector_pane_widths_are_fixed_from_terminal_width(self) -> None:
        left_width, right_width = calculate_selector_pane_widths(120)

        self.assertEqual(left_width, 58)
        self.assertEqual(right_width, 59)
        self.assertEqual(
            left_width + right_width + SELECTOR_PANE_GAP_WIDTH * 2 + 1,
            120,
        )

    def test_page_navigation_moves_active_pane_by_page(self) -> None:
        refs = [
            RemoteRepositoryRef(
                "github",
                f"repo-{index}",
                f"org/repo-{index}",
                "https://a.git",
                "",
                "",
                "main",
            )
            for index in range(20)
        ]
        state = RepositorySelectorState(
            refs,
            branch_loader=lambda _ref: [
                f"branch-{index}" for index in range(20)
            ],
        )

        state.page_down(page_size=5)
        self.assertEqual(state.cursor, 5)
        state.page_up(page_size=3)
        self.assertEqual(state.cursor, 2)

        state.activate_branch_pane()
        state.page_down(page_size=7)
        self.assertEqual(state.branch_cursor, 7)
        state.page_up(page_size=4)
        self.assertEqual(state.branch_cursor, 3)

    def test_footer_documents_page_navigation_keys(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://a.git",
            "",
            "",
            "main",
        )
        state = RepositorySelectorState([ref], branch_loader=lambda _ref: ["main"])

        self.assertEqual(
            state.render_footer(),
            "\n".join(
                [
                    "Search: type filter | ctrl-l clear",
                    "Move: up/down line | pgup/pgdown page | tab/right branches",
                    (
                        "Action: space select repo | ctrl-a select visible | "
                        "ctrl-u unselect visible | enter confirm | esc/ctrl-c cancel"
                    ),
                ]
            ),
        )

        state.activate_branch_pane()

        self.assertEqual(
            state.render_footer(),
            "\n".join(
                [
                    "Search: type filter | ctrl-l clear",
                    "Move: up/down line | pgup/pgdown page | shift-tab/left repos",
                    "Action: space select branch | enter confirm | esc/ctrl-c cancel",
                ]
            ),
        )

    def test_unselect_visible_removes_only_visible_repo_selection(self) -> None:
        refs = [
            RemoteRepositoryRef(
                "github",
                "alpha",
                "org/alpha",
                "https://a.git",
                "",
                "",
                "main",
            ),
            RemoteRepositoryRef(
                "github",
                "beta",
                "org/beta",
                "https://b.git",
                "",
                "",
                "main",
            ),
            RemoteRepositoryRef(
                "github",
                "gamma",
                "org/gamma",
                "https://c.git",
                "",
                "",
                "main",
            ),
        ]
        state = RepositorySelectorState(refs)
        state.select_visible()

        state.set_query("beta")
        state.unselect_visible()

        self.assertEqual(state.selected_refs, [refs[0], refs[2]])

    def test_unselect_visible_is_repo_pane_only(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://a.git",
            "",
            "",
            "main",
        )
        state = RepositorySelectorState([ref], branch_loader=lambda _ref: ["main"])
        state.select_visible()

        state.activate_branch_pane()
        state.unselect_visible()

        self.assertEqual(state.selected_refs, [ref])

    def test_run_repository_selector_initializes_body_before_app_binding(self) -> None:
        class _FakeEvent:
            def __iadd__(self, _handler: object) -> "_FakeEvent":
                return self

        class _FakeBuffer:
            def __init__(self) -> None:
                self.on_text_changed = _FakeEvent()
                self.text = ""

        class _FakeTextArea:
            def __init__(self, **_kwargs: object) -> None:
                self.buffer = _FakeBuffer()

        class _FakeFormattedTextControl:
            def __init__(self, callback: object) -> None:
                self.callback = callback

        class _FakeWindow:
            def __init__(self, **_kwargs: object) -> None:
                # The fake only needs constructor compatibility for layout wiring.
                pass

        class _FakeSplit:
            def __init__(self, children: list[object]) -> None:
                self.children = children

        class _FakeDynamicContainer:
            def __init__(self, callback: Callable[[], object]) -> None:
                callback()

        class _FakeLayout:
            def __init__(self, container: object) -> None:
                self.container = container

        class _FakeKeyBindings:
            def add(self, *_args: object, **_kwargs: object):
                def decorator(func: object) -> object:
                    return func

                return decorator

        class _FakeDimension:
            @staticmethod
            def exact(value: int) -> int:
                return value

        class _FakeApplication:
            def __init__(self, **_kwargs: object) -> None:
                # The test only verifies early initialization, not app behavior.
                pass

            def run(self) -> None:
                return None

        fake_modules: dict[str, Any] = {
            "prompt_toolkit": types.ModuleType("prompt_toolkit"),
            "prompt_toolkit.application": types.ModuleType(
                "prompt_toolkit.application"
            ),
            "prompt_toolkit.key_binding": types.ModuleType(
                "prompt_toolkit.key_binding"
            ),
            "prompt_toolkit.layout": types.ModuleType("prompt_toolkit.layout"),
            "prompt_toolkit.layout.containers": types.ModuleType(
                "prompt_toolkit.layout.containers"
            ),
            "prompt_toolkit.layout.controls": types.ModuleType(
                "prompt_toolkit.layout.controls"
            ),
            "prompt_toolkit.layout.dimension": types.ModuleType(
                "prompt_toolkit.layout.dimension"
            ),
            "prompt_toolkit.widgets": types.ModuleType("prompt_toolkit.widgets"),
        }
        cast(Any, fake_modules["prompt_toolkit.application"]).Application = (
            _FakeApplication
        )
        cast(Any, fake_modules["prompt_toolkit.key_binding"]).KeyBindings = (
            _FakeKeyBindings
        )
        cast(Any, fake_modules["prompt_toolkit.layout"]).HSplit = _FakeSplit
        cast(Any, fake_modules["prompt_toolkit.layout"]).Layout = _FakeLayout
        cast(Any, fake_modules["prompt_toolkit.layout"]).VSplit = _FakeSplit
        cast(Any, fake_modules["prompt_toolkit.layout"]).Window = _FakeWindow
        cast(Any, fake_modules["prompt_toolkit.layout.containers"]).DynamicContainer = (
            _FakeDynamicContainer
        )
        cast(Any, fake_modules["prompt_toolkit.layout.controls"]).FormattedTextControl = (
            _FakeFormattedTextControl
        )
        cast(Any, fake_modules["prompt_toolkit.layout.dimension"]).Dimension = (
            _FakeDimension
        )
        cast(Any, fake_modules["prompt_toolkit.widgets"]).TextArea = _FakeTextArea

        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://a.git",
            "",
            "",
            "main",
        )

        with patch.dict(sys.modules, fake_modules):
            with self.assertRaises(TuiSelectionCancelled):
                run_repository_selector([ref])


if __name__ == "__main__":
    unittest.main()
