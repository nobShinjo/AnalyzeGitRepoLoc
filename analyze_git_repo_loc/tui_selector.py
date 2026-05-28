"""
Terminal repository selector for remote repository refs.

Description:
    Provides a terminal-independent selection state and a prompt_toolkit-backed
    UI entry point. The UI imports prompt_toolkit lazily so non-TUI CLI use does
    not require terminal rendering dependencies at import time.
Classes:
    TuiSelectionCancelled:
        Raised when the user cancels repository selection.
    RepositorySelectionResult:
        Selected repositories plus branch choices.
    RepositorySelectorState:
        Search, cursor, and multi-selection state for repository and branch refs.
Functions:
    calculate_selector_pane_widths:
        Calculate stable repository and branch pane widths.
    choose_selector_layout_orientation:
        Select horizontal or vertical body layout for the terminal width.
    run_repository_selector:
        Open the interactive selector and return selected repository refs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from analyze_git_repo_loc.remote_catalog import RemoteRepositoryRef

SELECTOR_HORIZONTAL_MIN_WIDTH = 100
SELECTOR_PANE_GAP_WIDTH = 1
SELECTOR_VERTICAL_SEPARATOR_CHAR = "│"


class TuiSelectionCancelled(ValueError):
    """The repository selector was cancelled."""


@dataclass(frozen=True)
class RepositorySelectionResult:
    """Selected repositories and requested follow-up editor state."""

    selected_refs: list[RemoteRepositoryRef]
    branch_selection_requested: bool = False
    selected_branches: dict[str, str] = field(default_factory=dict)


def choose_selector_layout_orientation(width: int) -> Literal["horizontal", "vertical"]:
    """
    Choose the selector body layout for a terminal width.

    Args:
        width (int): Terminal column count.

    Returns:
        Literal["horizontal", "vertical"]: Horizontal when wide enough.
    """
    if width >= SELECTOR_HORIZONTAL_MIN_WIDTH:
        return "horizontal"
    return "vertical"


def calculate_selector_pane_widths(width: int) -> tuple[int, int]:
    """
    Calculate stable left and right pane widths for a terminal width.

    Args:
        width (int): Terminal column count.

    Returns:
        tuple[int, int]: Repository pane width and branch pane width.
    """
    separator_width = SELECTOR_PANE_GAP_WIDTH * 2 + 1
    content_width = max(2, width - separator_width)
    left_width = content_width // 2
    right_width = content_width - left_width
    return left_width, right_width


@dataclass
class RepositorySelectorState:
    """Search, cursor, and multi-selection state for repositories and branches."""

    repositories: list[RemoteRepositoryRef]
    branch_loader: Callable[[RemoteRepositoryRef], list[str]] | None = None
    query: str = ""
    cursor: int = 0
    active_pane: Literal["repositories", "branches"] = "repositories"
    branch_cursors: dict[str, int] = field(default_factory=dict)
    branch_cache: dict[str, list[str]] = field(default_factory=dict)
    branch_errors: dict[str, str] = field(default_factory=dict)
    selected_branches: dict[str, str] = field(default_factory=dict)
    selected_indexes: set[int] = field(default_factory=set)
    confirmed: bool = False
    cancelled: bool = False
    branch_selection_requested: bool = False

    @property
    def visible_indexes(self) -> list[int]:
        """Indexes matching the current search query."""
        if self.active_pane != "repositories":
            return list(range(len(self.repositories)))
        query = self.query.casefold().strip()
        if not query:
            return list(range(len(self.repositories)))
        visible: list[int] = []
        for index, ref in enumerate(self.repositories):
            haystack = f"{ref.provider} {ref.full_name} {ref.web_url}".casefold()
            if query in haystack:
                visible.append(index)
        return visible

    @property
    def visible_refs(self) -> list[RemoteRepositoryRef]:
        """Repository refs matching the current search query."""
        return [self.repositories[index] for index in self.visible_indexes]

    @property
    def selected_refs(self) -> list[RemoteRepositoryRef]:
        """Selected repository refs in original list order."""
        return [
            self.repositories[index]
            for index in range(len(self.repositories))
            if index in self.selected_indexes
        ]

    @property
    def current_ref(self) -> RemoteRepositoryRef | None:
        """Repository under the left-pane cursor."""
        indexes = self.visible_indexes
        if not indexes:
            return None
        return self.repositories[indexes[self.cursor]]

    @property
    def visible_branches(self) -> list[str]:
        """Branches matching the current branch search query."""
        ref = self.current_ref
        if ref is None:
            return []
        branches = self._branches_for(ref)
        query = self.query.casefold().strip() if self.active_pane == "branches" else ""
        if not query:
            return branches
        return [branch for branch in branches if query in branch.casefold()]

    @property
    def branch_cursor(self) -> int:
        """Cursor for the current repository branch list."""
        ref = self.current_ref
        if ref is None:
            return 0
        return self.branch_cursors.get(ref.full_name, 0)

    @branch_cursor.setter
    def branch_cursor(self, value: int) -> None:
        ref = self.current_ref
        if ref is None:
            return
        self.branch_cursors[ref.full_name] = value

    def set_query(self, query: str) -> None:
        """
        Set the search query and clamp cursor to the filtered list.

        Args:
            query (str): Search query.
        """
        self.query = query
        self._clamp_cursor()

    def move_up(self, amount: int = 1) -> None:
        """Move the active cursor upward in the visible list."""
        if self.active_pane == "branches":
            self._move_branch_up(amount)
            return
        visible_count = len(self.visible_indexes)
        if visible_count == 0:
            self.cursor = 0
            return
        self.cursor = max(0, self.cursor - amount)

    def move_down(self, amount: int = 1) -> None:
        """Move the active cursor downward in the visible list."""
        if self.active_pane == "branches":
            self._move_branch_down(amount)
            return
        visible_count = len(self.visible_indexes)
        if visible_count == 0:
            self.cursor = 0
            return
        self.cursor = min(visible_count - 1, self.cursor + amount)

    def page_up(self, page_size: int = 10) -> None:
        """Move the cursor up by a page."""
        self.move_up(page_size)

    def page_down(self, page_size: int = 10) -> None:
        """Move the cursor down by a page."""
        self.move_down(page_size)

    def toggle_current(self) -> None:
        """Toggle selection for the current active-pane item."""
        if self.active_pane == "branches":
            self.select_current_branch()
            return
        visible = self.visible_indexes
        if not visible:
            return
        index = visible[self.cursor]
        if index in self.selected_indexes:
            self.selected_indexes.remove(index)
        else:
            self.selected_indexes.add(index)

    def select_visible(self) -> None:
        """Select all currently visible repositories."""
        if self.active_pane != "repositories":
            return
        self.selected_indexes.update(self.visible_indexes)

    def unselect_visible(self) -> None:
        """Unselect all currently visible repositories."""
        if self.active_pane != "repositories":
            return
        self.selected_indexes.difference_update(self.visible_indexes)

    def clear_selection(self) -> None:
        """Clear the active search query."""
        self.query = ""
        self._clamp_cursor()

    def confirm(self) -> None:
        """Confirm the current selection."""
        self.confirmed = True

    def request_branch_selection(self) -> None:
        """Move focus to the branch pane."""
        self.activate_branch_pane()

    def activate_branch_pane(self) -> None:
        """Focus the branch pane and fetch branches for the cursor repo."""
        visible = self.visible_indexes
        if not visible:
            return
        self.cursor = visible[self.cursor]
        ref = self.repositories[self.cursor]
        self.active_pane = "branches"
        self.query = ""
        self._branches_for(ref)
        self._clamp_cursor()

    def activate_repository_pane(self) -> None:
        """Focus the repository pane."""
        self.active_pane = "repositories"
        self.query = ""
        self._clamp_cursor()

    def select_current_branch(self) -> None:
        """Select the highlighted branch for the cursor repository."""
        ref = self.current_ref
        if ref is None:
            return
        branches = self.visible_branches
        if not branches:
            return
        self.selected_branches[ref.full_name] = branches[self.branch_cursor]

    def selected_branch_for(self, ref: RemoteRepositoryRef) -> str:
        """Return the selected or default branch for a repository."""
        return self.selected_branches.get(ref.full_name) or ref.default_branch or "main"

    def branch_status_for(self, ref: RemoteRepositoryRef) -> str:
        """Return the branch-loading status label for a repository."""
        if ref.full_name in self.branch_errors:
            return "Failed to load branches; using default branch"
        if ref.full_name in self.branch_cache:
            return f"{len(self.branch_cache[ref.full_name])} branches"
        return "Not loaded"

    def cancel(self) -> None:
        """Cancel repository selection."""
        self.cancelled = True

    def render(self, *, height: int = 18) -> str:
        """
        Render the selector state as terminal text.

        Args:
            height (int): Maximum number of repository rows to render.

        Returns:
            str: Display text.
        """
        return "\n".join(
            [
                self.render_header(),
                "",
                self.render_repositories(height=height),
                "",
                self.render_branches(height=height),
                "",
                self.render_footer(),
            ]
        )

    def render_header(self) -> str:
        """Render the selector title and active search state."""
        visible = self.visible_indexes
        selected_count = len(self.selected_indexes)
        return "\n".join(
            [
                "GitHub/GitLab Repository Selector",
                f"{self.active_pane.title()} search: {self.query or '(none)'}",
                (
                    f"Visible: {len(visible)} / {len(self.repositories)}  "
                    f"Selected: {selected_count}"
                ),
            ]
        )

    def render_repositories(self, *, height: int = 18) -> str:
        """Render only the repository pane."""
        visible = self.visible_indexes
        lines = ["Repositories" + (" *" if self.active_pane == "repositories" else "")]
        if not visible:
            lines.append("No repositories match the current search.")
            return "\n".join(lines)

        start = max(0, min(self.cursor - height // 2, max(0, len(visible) - height)))
        end = min(len(visible), start + height)
        for visible_position, index in enumerate(visible[start:end], start=start):
            ref = self.repositories[index]
            cursor = ">" if visible_position == self.cursor else " "
            checked = "x" if index in self.selected_indexes else " "
            branch = self.selected_branch_for(ref)
            lines.append(
                f"{cursor} [{checked}] {ref.provider:<6} {ref.full_name} "
                f"({branch})"
            )
        return "\n".join(lines)

    def render_branches(self, *, height: int = 18) -> str:
        """Render only the branch pane for the cursor repository."""
        current = self.current_ref
        lines = ["Branches" + (" *" if self.active_pane == "branches" else "")]
        if current is None:
            lines.append("No repository selected for branch display.")
        else:
            lines.append(f"Branches: {current.full_name}")
            lines.append(self.branch_status_for(current))
            branches = self.visible_branches
            if not branches:
                lines.append("No branches match the current search.")
            else:
                branch_start = max(
                    0,
                    min(
                        self.branch_cursor - height // 2,
                        max(0, len(branches) - height),
                    ),
                )
                branch_end = min(len(branches), branch_start + height)
                selected_branch = self.selected_branch_for(current)
                for branch_position, branch in enumerate(
                    branches[branch_start:branch_end],
                    start=branch_start,
                ):
                    cursor = ">" if branch_position == self.branch_cursor else " "
                    checked = "x" if branch == selected_branch else " "
                    lines.append(f"{cursor} [{checked}] {branch}")
        return "\n".join(lines)

    def render_footer(self) -> str:
        """Render active-pane key help."""
        if self.active_pane == "repositories":
            help_lines = [
                "Search: type filter | ctrl-l clear",
                "Move: up/down line | pgup/pgdown page | tab/right branches",
                "Action: space select repo | ctrl-a select visible | ctrl-u unselect visible | enter confirm | esc/ctrl-c cancel",
            ]
        else:
            help_lines = [
                "Search: type filter | ctrl-l clear",
                "Move: up/down line | pgup/pgdown page | shift-tab/left repos",
                "Action: space select branch | enter confirm | esc/ctrl-c cancel",
            ]
        return "\n".join(help_lines)

    def _clamp_cursor(self) -> None:
        if self.active_pane == "branches":
            branch_count = len(self.visible_branches)
            if branch_count == 0:
                self.branch_cursor = 0
            else:
                self.branch_cursor = min(self.branch_cursor, branch_count - 1)
            return
        visible_count = len(self.visible_indexes)
        if visible_count == 0:
            self.cursor = 0
        else:
            self.cursor = min(self.cursor, visible_count - 1)

    def _branches_for(self, ref: RemoteRepositoryRef) -> list[str]:
        if ref.full_name in self.branch_cache:
            return self.branch_cache[ref.full_name]
        fallback = [ref.default_branch or "main"]
        if self.branch_loader is None:
            self.branch_cache[ref.full_name] = fallback
            return fallback
        try:
            branches = self.branch_loader(ref)
        except Exception as ex:
            self.branch_errors[ref.full_name] = str(ex)
            self.branch_cache[ref.full_name] = fallback
            return fallback
        normalized = [branch for branch in branches if branch]
        if not normalized:
            normalized = fallback
        self.branch_cache[ref.full_name] = normalized
        return normalized

    def _move_branch_up(self, amount: int) -> None:
        visible_count = len(self.visible_branches)
        if visible_count == 0:
            self.branch_cursor = 0
            return
        self.branch_cursor = max(0, self.branch_cursor - amount)

    def _move_branch_down(self, amount: int) -> None:
        visible_count = len(self.visible_branches)
        if visible_count == 0:
            self.branch_cursor = 0
            return
        self.branch_cursor = min(visible_count - 1, self.branch_cursor + amount)


def run_repository_selector(
    repositories: list[RemoteRepositoryRef],
    *,
    branch_loader: Callable[[RemoteRepositoryRef], list[str]] | None = None,
    return_result: bool = False,
) -> list[RemoteRepositoryRef] | RepositorySelectionResult:
    """
    Run the prompt_toolkit-backed repository selector.

    Args:
        repositories (list[RemoteRepositoryRef]): Repositories to select from.
        branch_loader (Callable[[RemoteRepositoryRef], list[str]] | None): Lazy branch loader.
        return_result (bool): Return branch metadata with selected refs.

    Returns:
        list[RemoteRepositoryRef] | RepositorySelectionResult: Selected repositories.

    Raises:
        TuiSelectionCancelled: If the user cancels or confirms no selection.
        RuntimeError: If prompt_toolkit is not installed.
    """
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
        from prompt_toolkit.layout.containers import DynamicContainer
        from prompt_toolkit.layout.dimension import Dimension
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.widgets import TextArea
    except ImportError as ex:
        raise RuntimeError(
            "prompt_toolkit is required for interactive runs. "
            "Install dependencies with `uv sync --active`."
        ) from ex

    state = RepositorySelectorState(repositories, branch_loader=branch_loader)
    search_field = TextArea(
        height=1,
        prompt="Search: ",
        multiline=False,
    )
    search_field.buffer.on_text_changed += lambda buffer: state.set_query(buffer.text)
    header_control = FormattedTextControl(lambda: state.render_header())
    repository_control = FormattedTextControl(lambda: state.render_repositories())
    branch_control = FormattedTextControl(lambda: state.render_branches())
    footer_control = FormattedTextControl(lambda: state.render_footer())
    kb = KeyBindings()
    app: Application | None = None

    def _body_container() -> HSplit | VSplit:
        if app is None:
            orientation: Literal["horizontal", "vertical"] = "horizontal"
        else:
            terminal_width = app.output.get_size().columns
            orientation = choose_selector_layout_orientation(terminal_width)
        if orientation == "horizontal":
            if app is None:
                left_width, right_width = calculate_selector_pane_widths(
                    SELECTOR_HORIZONTAL_MIN_WIDTH
                )
            else:
                left_width, right_width = calculate_selector_pane_widths(
                    app.output.get_size().columns
                )
            return VSplit(
                [
                    Window(
                        content=repository_control,
                        width=Dimension.exact(left_width),
                        always_hide_cursor=True,
                    ),
                    Window(
                        width=SELECTOR_PANE_GAP_WIDTH,
                        char=" ",
                        always_hide_cursor=True,
                    ),
                    Window(
                        width=1,
                        char=SELECTOR_VERTICAL_SEPARATOR_CHAR,
                        always_hide_cursor=True,
                    ),
                    Window(
                        width=SELECTOR_PANE_GAP_WIDTH,
                        char=" ",
                        always_hide_cursor=True,
                    ),
                    Window(
                        content=branch_control,
                        width=Dimension.exact(right_width),
                        always_hide_cursor=True,
                    ),
                ]
            )
        return HSplit(
            [
                Window(content=repository_control, always_hide_cursor=True),
                Window(height=1, char="-", always_hide_cursor=True),
                Window(content=branch_control, always_hide_cursor=True),
            ]
        )

    @kb.add("up")
    def _(_: object) -> None:
        state.move_up()

    @kb.add("down")
    def _(_: object) -> None:
        state.move_down()

    @kb.add("pageup", eager=True)
    def _(_: object) -> None:
        state.page_up()

    @kb.add("pagedown", eager=True)
    def _(_: object) -> None:
        state.page_down()

    @kb.add(" ")
    def _(_: object) -> None:
        state.toggle_current()

    @kb.add("c-a")
    def _(_: object) -> None:
        state.select_visible()

    @kb.add("c-u")
    def _(_: object) -> None:
        state.unselect_visible()

    @kb.add("c-l")
    def _(_: object) -> None:
        state.clear_selection()
        search_field.buffer.text = ""

    @kb.add("enter")
    def _(_: object) -> None:
        state.confirm()
        if app is not None:
            app.exit()

    @kb.add("tab")
    @kb.add("right")
    def _(_: object) -> None:
        state.request_branch_selection()
        search_field.buffer.text = ""

    @kb.add("s-tab")
    @kb.add("left")
    def _(_: object) -> None:
        state.activate_repository_pane()
        search_field.buffer.text = ""

    @kb.add("escape")
    @kb.add("c-c")
    def _(_: object) -> None:
        state.cancel()
        if app is not None:
            app.exit()

    app = Application(
        layout=Layout(
            HSplit(
                [
                    search_field,
                    Window(content=header_control, height=3, always_hide_cursor=True),
                    DynamicContainer(_body_container),
                    Window(content=footer_control, height=3, always_hide_cursor=True),
                ]
            )
        ),
        key_bindings=kb,
        full_screen=True,
    )
    app.run()
    if state.cancelled or not state.selected_refs:
        raise TuiSelectionCancelled("Repository selection cancelled.")
    if return_result:
        return RepositorySelectionResult(
            selected_refs=state.selected_refs,
            branch_selection_requested=state.branch_selection_requested,
            selected_branches={
                ref.full_name: state.selected_branch_for(ref)
                for ref in state.selected_refs
            },
        )
    return state.selected_refs
