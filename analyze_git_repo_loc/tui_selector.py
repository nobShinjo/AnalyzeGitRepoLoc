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
        Selected repositories plus follow-up branch selection intent.
    RepositorySelectorState:
        Search, cursor, and multi-selection state for repository refs.
Functions:
    run_repository_selector:
        Open the interactive selector and return selected repository refs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from analyze_git_repo_loc.remote_catalog import RemoteRepositoryRef


class TuiSelectionCancelled(ValueError):
    """The repository selector was cancelled."""


@dataclass(frozen=True)
class RepositorySelectionResult:
    """Selected repositories and requested follow-up editor state."""

    selected_refs: list[RemoteRepositoryRef]
    branch_selection_requested: bool = False


@dataclass
class RepositorySelectorState:
    """Search, cursor, and multi-selection state for repositories."""

    repositories: list[RemoteRepositoryRef]
    query: str = ""
    cursor: int = 0
    selected_indexes: set[int] = field(default_factory=set)
    confirmed: bool = False
    cancelled: bool = False
    branch_selection_requested: bool = False

    @property
    def visible_indexes(self) -> list[int]:
        """Indexes matching the current search query."""
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

    def set_query(self, query: str) -> None:
        """
        Set the search query and clamp cursor to the filtered list.

        Args:
            query (str): Search query.
        """
        self.query = query
        self._clamp_cursor()

    def move_up(self, amount: int = 1) -> None:
        """Move the cursor upward in the visible list."""
        visible_count = len(self.visible_indexes)
        if visible_count == 0:
            self.cursor = 0
            return
        self.cursor = max(0, self.cursor - amount)

    def move_down(self, amount: int = 1) -> None:
        """Move the cursor downward in the visible list."""
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
        """Toggle selection for the current visible repository."""
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
        self.selected_indexes.update(self.visible_indexes)

    def clear_selection(self) -> None:
        """Clear all selected repositories."""
        self.selected_indexes.clear()

    def confirm(self) -> None:
        """Confirm the current selection."""
        self.confirmed = True

    def request_branch_selection(self) -> None:
        """Confirm selection and request branch editing as the next step."""
        self.branch_selection_requested = True
        self.confirm()

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
        visible = self.visible_indexes
        selected_count = len(self.selected_indexes)
        lines = [
            "GitHub/GitLab Repository Selector",
            f"Search: {self.query or '(none)'}",
            f"Visible: {len(visible)} / {len(self.repositories)}  Selected: {selected_count}",
            "",
        ]
        if not visible:
            lines.append("No repositories match the current search.")
            return "\n".join(lines)

        start = max(0, min(self.cursor - height // 2, max(0, len(visible) - height)))
        end = min(len(visible), start + height)
        for visible_position, index in enumerate(visible[start:end], start=start):
            ref = self.repositories[index]
            cursor = ">" if visible_position == self.cursor else " "
            checked = "x" if index in self.selected_indexes else " "
            lines.append(
                f"{cursor} [{checked}] {ref.provider:<6} {ref.full_name} "
                f"({ref.default_branch or 'main'})"
            )
        lines.extend(
            [
                "",
                "Keys: type to search, up/down move, space toggle,",
                "      ctrl-a select visible, ctrl-l clear, enter confirm,",
                "      tab branches, esc or ctrl-c cancel",
            ]
        )
        return "\n".join(lines)

    def _clamp_cursor(self) -> None:
        visible_count = len(self.visible_indexes)
        if visible_count == 0:
            self.cursor = 0
        else:
            self.cursor = min(self.cursor, visible_count - 1)


def run_repository_selector(
    repositories: list[RemoteRepositoryRef],
    *,
    return_result: bool = False,
) -> list[RemoteRepositoryRef] | RepositorySelectionResult:
    """
    Run the prompt_toolkit-backed repository selector.

    Args:
        repositories (list[RemoteRepositoryRef]): Repositories to select from.

    Returns:
        list[RemoteRepositoryRef]: Selected repositories.

    Raises:
        TuiSelectionCancelled: If the user cancels or confirms no selection.
        RuntimeError: If prompt_toolkit is not installed.
    """
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.widgets import TextArea
    except ImportError as ex:
        raise RuntimeError(
            "prompt_toolkit is required for interactive runs. "
            "Install dependencies with `uv sync --active`."
        ) from ex

    state = RepositorySelectorState(repositories)
    search_field = TextArea(
        height=1,
        prompt="Search: ",
        multiline=False,
    )
    search_field.buffer.on_text_changed += lambda buffer: state.set_query(buffer.text)
    control = FormattedTextControl(lambda: state.render())
    kb = KeyBindings()
    app: Application | None = None

    @kb.add("up")
    def _(_: object) -> None:
        state.move_up()

    @kb.add("down")
    def _(_: object) -> None:
        state.move_down()

    @kb.add("pageup")
    def _(_: object) -> None:
        state.page_up()

    @kb.add("pagedown")
    def _(_: object) -> None:
        state.page_down()

    @kb.add(" ")
    def _(_: object) -> None:
        state.toggle_current()

    @kb.add("c-a")
    def _(_: object) -> None:
        state.select_visible()

    @kb.add("c-l")
    def _(_: object) -> None:
        state.clear_selection()

    @kb.add("enter")
    def _(_: object) -> None:
        state.confirm()
        if app is not None:
            app.exit()

    @kb.add("tab")
    def _(_: object) -> None:
        state.request_branch_selection()
        if app is not None:
            app.exit()

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
                    Window(content=control, always_hide_cursor=True),
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
        )
    return state.selected_refs
