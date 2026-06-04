"""Repository progress bar helpers.

Description:
    Centralizes repository child-progress event handling used by multi-repo
    analysis. The helpers are intentionally small and side-effect focused so
    the analysis runner can stay readable.
Functions:
    emit_repo_progress:
        Send repository progress events to a queue when one is configured.
    apply_repo_progress_event:
        Apply a single repository progress event to a tqdm child bar.
    start_repo_progress_listener:
        Start the listener thread that consumes repository progress events.
"""

from __future__ import annotations

import queue as queue_module
from threading import Event, Thread
from typing import Protocol, TypeAlias

from tqdm import tqdm

from analyze_git_repo_loc.i18n import tr

RepoProgressEvent: TypeAlias = tuple[str, int, str, int]


class ProgressQueue(Protocol):
    """Queue interface used by repository progress helpers."""

    def put(self, item: RepoProgressEvent) -> object:
        """Store a repository progress event."""
        raise NotImplementedError

    def get(
        self,
        block: bool = True,
        timeout: float | None = None,
    ) -> RepoProgressEvent:
        """Read a repository progress event."""
        raise NotImplementedError


REPO_EVENT_START = "start"
REPO_EVENT_SCAN_TOTAL = "scan_total"
REPO_EVENT_SCAN_ADVANCE = "scan_advance"
REPO_EVENT_TOTAL = "total"
REPO_EVENT_ADVANCE = "advance"
REPO_EVENT_FINISH = "finish"
REPO_EVENT_STOP = "stop"
REPO_PROGRESS_LABEL_WIDTH = 32
REPO_PROGRESS_STATUS_WIDTH = len("analyzing commits")
REPO_PROGRESS_COUNT_WIDTH = 5
REPO_PROGRESS_BAR_FORMAT = (
    f"{{desc}}: {{percentage:3.0f}}%|{{bar}}| "
    f"{{n_fmt:>{REPO_PROGRESS_COUNT_WIDTH}}}/"
    f"{{total_fmt:>{REPO_PROGRESS_COUNT_WIDTH}}} "
    "[{elapsed}<{remaining}, {rate_fmt}]"
)


def emit_repo_progress(
    progress_queue: ProgressQueue | None,
    kind: str,
    repository_index: int,
    repository_name: str,
    value: int = 0,
) -> None:
    """Emit a repository progress event when configured."""
    if progress_queue is None:
        return
    try:
        progress_queue.put((kind, repository_index, repository_name, value))
    except AttributeError, EOFError, OSError, ValueError:
        return


def truncate_repo_label(name: str, max_width: int) -> str:
    """Truncate a repository label to fit within a width constraint."""
    if len(name) <= max_width:
        return name
    if max_width <= 3:
        return "." * max(0, max_width)
    trimmed = name[: max(0, max_width - 3)]
    return trimmed + "..."


def format_repo_progress_description(label: str, status: str) -> str:
    """Format a fixed-width repository child progress description."""
    fixed_label = truncate_repo_label(label, REPO_PROGRESS_LABEL_WIDTH)
    return (
        f"  Repo: {fixed_label:<{REPO_PROGRESS_LABEL_WIDTH}} "
        f"({status:<{REPO_PROGRESS_STATUS_WIDTH}})"
    )


def _advance_bar(progress_bar: tqdm | None, value: int) -> None:
    """Advance a child progress bar by a positive integer value."""
    if progress_bar is None:
        return
    step = max(0, int(value))
    if step:
        progress_bar.update(step)


def apply_repo_progress_event(
    *,
    kind: str,
    bar: tqdm | None,
    label: str,
    value: int,
) -> bool:
    """Apply a repository progress event to a child progress bar."""
    if kind == REPO_EVENT_STOP:
        return False
    if bar is None:
        return True
    if kind == REPO_EVENT_START:
        bar.set_description_str(
            format_repo_progress_description(
                label,
                tr("progress.repo.status.getting_commits"),
            )
        )
        bar.refresh()
    elif kind == REPO_EVENT_SCAN_TOTAL:
        total = max(0, int(value))
        bar.set_description_str(
            format_repo_progress_description(
                label,
                tr("progress.repo.status.getting_commits"),
            )
        )
        bar.total = total
        bar.n = 0
        bar.refresh()
    elif kind == REPO_EVENT_SCAN_ADVANCE:
        _advance_bar(bar, value)
    elif kind == REPO_EVENT_TOTAL:
        total = max(0, int(value))
        bar.set_description_str(
            format_repo_progress_description(
                label,
                tr("progress.repo.status.analyzing_commits"),
            )
        )
        bar.total = total
        bar.n = 0
        bar.refresh()
    elif kind == REPO_EVENT_ADVANCE:
        _advance_bar(bar, value)
    elif kind == REPO_EVENT_FINISH:
        if bar.total is not None and bar.n < bar.total:
            bar.update(bar.total - bar.n)
        bar.set_description_str(
            format_repo_progress_description(label, tr("progress.repo.status.done"))
        )
        bar.refresh()
    return True


def start_repo_progress_listener(
    *,
    progress_queue: ProgressQueue,
    repo_bars: dict[int, tqdm],
    repo_labels: dict[int, str],
) -> tuple[Event, Thread]:
    """Start a background listener that updates repository child progress bars."""
    stop_event = Event()

    def loop() -> None:
        while True:
            try:
                kind, repository_index, repository_name, value = progress_queue.get(
                    timeout=0.1
                )
            except queue_module.Empty:
                if stop_event.is_set():
                    break
                continue
            progress_bar = repo_bars.get(repository_index)
            label = repo_labels.get(repository_index) or repository_name
            if not apply_repo_progress_event(
                kind=kind,
                bar=progress_bar,
                label=label,
                value=value,
            ):
                break

    thread = Thread(target=loop, daemon=True)
    thread.start()
    return stop_event, thread
