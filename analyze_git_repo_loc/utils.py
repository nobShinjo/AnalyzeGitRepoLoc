"""
This module provides utility functions for analyzing lines of code (LOC) in Git repositories.

Functions:
    parse_repos_paths(input_string: str) -> list[tuple[Path | str, str]]:
    parse_arguments(parser: argparse.ArgumentParser) -> argparse.Namespace:
        Parse command line arguments.
    handle_exception(ex: Exception) -> None:
    get_time_interval_and_period(interval: str) -> Union[str, str]:
    save_repository_branch_info(repo_paths, output_file: Path) -> None:
    analyze_trends(
    analyze_git_repositories(args: argparse.Namespace) -> list[pd.DataFrame]:
"""

import argparse
import os
import queue as queue_module
import shutil
import sys
import traceback
from concurrent.futures import (  # pylint: disable=no-name-in-module
    ProcessPoolExecutor,
    as_completed,
)
from datetime import date, datetime
from multiprocessing import Manager
from multiprocessing.managers import SyncManager
from pathlib import Path
from threading import Event, Thread

import pandas as pd
from tqdm import tqdm

from analyze_git_repo_loc.colored_console_printer import ColoredConsolePrinter
from analyze_git_repo_loc.git_repo_loc_analyzer import GitRepoLOCAnalyzer
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.remote_auth import RemoteAuthError
from analyze_git_repo_loc.remote_repos import RemoteRepoManager
from analyze_git_repo_loc.yaml_config import merge_yaml_config

_REMOTE_REPO_MANAGER = RemoteRepoManager()

_REPO_EVENT_START = "start"
_REPO_EVENT_SCAN_TOTAL = "scan_total"
_REPO_EVENT_SCAN_ADVANCE = "scan_advance"
_REPO_EVENT_TOTAL = "total"
_REPO_EVENT_ADVANCE = "advance"
_REPO_EVENT_FINISH = "finish"
_REPO_EVENT_STOP = "stop"
_REPO_PROGRESS_LABEL_WIDTH = 32


def parse_repos_paths(
    repo_paths_input: str,
) -> list[tuple[Path | str, str, list[Path]]]:
    """
    Parse repository paths, branches and excluded directories path from a string.

    Args:
        repo_paths_input (str): A comma-separated list of repository entries.
            Format for each entry: "repo_path#branch,/path/to/exclude1,/path/to/exclude2,..."

    Returns:
       list[tuple[Path | str, str, list[Path]]]: A list of tuples containing:
        - Path | str: Repository path (local path or remote URL)
        - str: Branch name
        - list[Path]: Excluded directories paths
    """
    path = Path(repo_paths_input)
    if path.is_file():
        raise ValueError(
            "Repository list files are no longer supported. "
            "Use --config with a YAML configuration file instead."
        )
    repo_entries = repo_paths_input.split(",")

    # Parse each line into repository path, branch name, and excluded directories
    result = []
    for line in repo_entries:
        parts = line.split(",")
        if len(parts) < 1:
            continue
        repo_and_branch = parts[0].split("#", 1)
        raw_repo = repo_and_branch[0].strip()
        repo_path = (
            raw_repo if _REMOTE_REPO_MANAGER.is_git_url(raw_repo) else Path(raw_repo)
        )
        branch_name = repo_and_branch[1].strip() if len(repo_and_branch) > 1 else "main"
        exclude_dirs = [Path(item.strip()) for item in parts[1:] if item.strip()]
        result.append((repo_path, branch_name, exclude_dirs))

    return result


def _normalize_optional_text(value: str | None) -> str | None:
    """
    Normalize optional CLI text input by trimming whitespace.

    Args:
        value (str | None): The text input to normalize.

    Returns:
        str | None: The normalized string or None if empty/whitespace.
    """
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_optional_list(values: list[str] | None) -> list[str] | None:
    """
    Normalize optional list input by trimming items and dropping empties.

    Args:
        values (list[str] | str | None): The list input to normalize.

    Returns:
        list[str] | None: Normalized items or None when unset/empty.
    """
    if values is None:
        return None
    if isinstance(values, str):
        values = [item.strip() for item in values.split(",")]
    if not isinstance(values, list):
        raise ValueError("Invalid list input; expected a list of strings.")
    normalized: list[str] = []
    for item in values:
        if item is None:
            continue
        if not isinstance(item, str):
            raise ValueError("List entries must be strings.")
        trimmed = item.strip()
        if trimmed:
            normalized.append(trimmed)
    return normalized or None


def _normalize_optional_int(value: int | str | None, label: str) -> int | None:
    """
    Normalize optional integer input by trimming and validating.

    Args:
        value (int | str | None): The input value to normalize.
        label (str): Label used in validation error messages.

    Returns:
        int | None: Normalized integer value or None when unset.
    """
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        value = normalized
    try:
        parsed = int(value)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"Invalid {label} value '{value}'. Use an integer.") from ex
    if parsed < 1:
        raise ValueError(f"Invalid {label} value '{value}'. Use 1 or higher.")
    return parsed


def _emit_repo_progress(
    progress_queue: object | None,
    kind: str,
    repository_index: int,
    repository_name: str,
    value: int = 0,
) -> None:
    """
    Emit a repository progress event when configured.

    Args:
        progress_queue (object | None): Queue-like object for events.
        kind (str): Event kind ("start", "total", "advance", or "finish").
        repository_index (int): Repository index for the event.
        repository_name (str): Repository name for the event.
        value (int): Optional value for total/advance events.
    """
    if progress_queue is None:
        return
    try:
        progress_queue.put((kind, repository_index, repository_name, value))
    except (AttributeError, EOFError, OSError, ValueError):
        # Ignore queue errors to avoid breaking analysis.
        return


def _truncate_repo_label(name: str, max_width: int) -> str:
    """
    Truncate a repository label to fit within a width constraint.

    Args:
        active_repos (list[str]): Active repository names.
        max_width (int): Maximum width for the formatted text.

    Returns:
        str: Formatted active repository list.
    """
    if len(name) <= max_width:
        return name
    trimmed = name[: max(0, max_width - 1)]
    return trimmed + "…"


def _apply_repo_progress_event(
    *,
    kind: str,
    bar: tqdm | None,
    label: str,
    value: int,
) -> bool:
    """
    Apply a repository progress event to a child progress bar.

    Args:
        kind (str): Event kind.
        bar (tqdm | None): Target progress bar, if available.
        label (str): Repository label for display.
        value (int): Event payload value.

    Returns:
        bool: True to continue listening, False to stop.
    """
    if kind == _REPO_EVENT_STOP:
        return False
    if bar is None:
        return True
    if kind == _REPO_EVENT_START:
        bar.set_description_str(f"Repo: {label} (getting commits)")
        bar.refresh()
    elif kind == _REPO_EVENT_SCAN_TOTAL:
        total = max(0, int(value))
        bar.set_description_str(f"Repo: {label} (getting commits)")
        bar.total = total
        bar.n = 0
        bar.refresh()
    elif kind == _REPO_EVENT_SCAN_ADVANCE:
        step = max(0, int(value))
        if step:
            bar.update(step)
    elif kind == _REPO_EVENT_TOTAL:
        total = max(0, int(value))
        bar.set_description_str(f"Repo: {label} (analyzing commits)")
        bar.total = total
        bar.n = 0
        bar.refresh()
    elif kind == _REPO_EVENT_ADVANCE:
        step = max(0, int(value))
        if step:
            bar.update(step)
    elif kind == _REPO_EVENT_FINISH:
        if bar.total is not None and bar.n < bar.total:
            bar.update(bar.total - bar.n)
        suffix = "done"
        if bar.total == 0:
            suffix = "done, 0 target commits"
        bar.set_description_str(f"Repo: {label} ({suffix})")
        bar.refresh()
    return True


def _start_repo_progress_listener(
    *,
    progress_queue: object,
    repo_bars: dict[int, tqdm],
    repo_labels: dict[int, str],
) -> tuple[Event, Thread]:
    """
    Start a background listener that updates repository child progress bars.

    Args:
        progress_queue (object): Queue-like object for events.
        repo_bars (dict[int, tqdm]): Repository progress bars by index.
        repo_labels (dict[int, str]): Repository labels by index.

    Returns:
        tuple[Event, Thread]: Stop event and listener thread.
    """
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
            bar = repo_bars.get(repository_index)
            label = repo_labels.get(repository_index, repository_name)
            if not _apply_repo_progress_event(
                kind=kind,
                bar=bar,
                label=label,
                value=value,
            ):
                break

    thread = Thread(target=loop, daemon=True)
    thread.start()
    return stop_event, thread


def _parse_optional_iso_date(
    value: str | date | datetime | None,
    label: str,
) -> datetime | None:
    """
    Parse an optional ISO date string into a datetime object.

    Args:
        value (str | date | datetime | None): The raw input.
    Returns:
        datetime | None: Parsed datetime or None when unset/empty.

    Raises:
        ValueError: If the date format is invalid.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if value is not None and not isinstance(value, str):
        raise ValueError(f"Invalid {label} date '{value}'. Use YYYY-MM-DD.")
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as ex:
        raise ValueError(f"Invalid {label} date '{value}'. Use YYYY-MM-DD.") from ex


def _validate_date_range(since: datetime | None, until: datetime | None) -> None:
    """
    Validate the date range for optional filters.

    Args:
        since (datetime | None): The start date.
        until (datetime | None): The end date.

    Raises:
        ValueError: If since is after until.
    """
    if since is not None and until is not None and since > until:
        raise ValueError("Invalid date range: --since must be on or before --until.")


def parse_arguments(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """
    parse_arguments Parse command line arguments.

    Args:
        parser (ArgumentParser): ArgumentParser object.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """
    parser.description = parser.description or tr("cli.description")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help=tr("cli.init_help"),
    )
    init_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yml"),
        help=tr("cli.init_config_help"),
    )
    init_parser.set_defaults(
        interactive=False,
        repo_paths=None,
        output=None,
        since=None,
        until=None,
        interval=None,
        lang=None,
        author_name=None,
        exclude_dirs=None,
        workers=None,
        clear_cache=None,
        no_plot_show=None,
    )

    run_parser = subparsers.add_parser(
        "run",
        help=tr("cli.run_help"),
    )
    run_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yml"),
        help=tr("cli.config_help"),
    )
    run_parser.add_argument("-o", "--output", type=Path, default=None, help=tr("cli.output_help"))
    run_parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        default=False,
        help=tr("cli.interactive_help"),
    )
    run_parser.add_argument(
        "--since",
        type=str,
        default=None,
        help=tr("cli.since_help"),
    )
    run_parser.add_argument(
        "--until",
        type=str,
        default=None,
        help=tr("cli.until_help"),
    )
    run_parser.add_argument(
        "--interval",
        choices=["daily", "weekly", "monthly"],
        default=None,
        help=tr("cli.interval_help"),
    )
    run_parser.add_argument(
        "--no-plot-show",
        action="store_true",
        default=None,
        help=tr("cli.no_plot_show_help"),
    )
    run_parser.set_defaults(
        repo_paths=None,
        lang=None,
        author_name=None,
        exclude_dirs=None,
        workers=None,
        clear_cache=None,
    )

    args = parser.parse_args()
    try:
        if args.command == "init":
            return args
        args = merge_yaml_config(
            args=args,
            repo_manager=_REMOTE_REPO_MANAGER,
            normalize_list=_normalize_optional_list,
        )
        args.since = _parse_optional_iso_date(args.since, "--since")
        args.until = _parse_optional_iso_date(args.until, "--until")
        args.lang = _normalize_optional_list(args.lang)
        args.author_name = _normalize_optional_list(args.author_name)
        args.exclude_dirs = _normalize_optional_list(args.exclude_dirs)
        args.workers = _normalize_optional_int(args.workers, "--workers")
        if args.clear_cache is None:
            args.clear_cache = False
        if args.no_plot_show is None:
            args.no_plot_show = False
        _validate_date_range(args.since, args.until)
    except ValueError as ex:
        parser.error(str(ex))
    return args


def handle_exception(ex: Exception) -> None:
    """
    Handle exceptions by printing the error message and exiting the program.

    Args:
        ex (Exception): The exception to handle.
    """
    if isinstance(ex, RemoteAuthError):
        tqdm.write(str(ex))
        sys.exit(1)
    print(tr("error.unexpected"), file=sys.stderr)
    print(tr("error.type", type=type(ex).__name__), file=sys.stderr)
    print(tr("error.message", message=str(ex)), file=sys.stderr)
    print(tr("error.stack_trace"), file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)


def get_time_interval_and_period(interval: str) -> tuple[str, str]:
    """
    Determines the time interval and period based on the provided arguments.

    Args:
        interval: A string representing the interval ('daily', 'weekly', or 'monthly').

    Returns:
        A tuple containing:
            - time_interval (str): A string representing the time interval
            ('Month', 'Week', or 'Date').
            - period (str): A string representing the period ('M', 'W', or 'D').

    Raises:
        ValueError: If the interval provided in args is not one of 'monthly', 'weekly', or 'daily'.
    """
    interval_map = {"monthly": "Month", "weekly": "Week", "daily": "Date"}
    if interval not in interval_map:
        raise ValueError(f"Invalid interval: {interval}")
    time_interval = interval_map[interval]
    period_dict = {"monthly": "M", "weekly": "W", "daily": "D"}
    period = period_dict[interval]
    return time_interval, period


def _resolve_analysis_repo_path(
    repo_path: Path | str, branch_name: str, cache_dir: Path
) -> Path | str:
    """
    Resolve the analysis path for a repository, cloning if needed.

    Args:
        repo_path (Path | str): Repository path or URL.
        branch_name (str): Branch to analyze.
        cache_dir (Path): Cache directory for remote clones.

    Returns:
        Path | str: Local path to analyze.
    """
    if isinstance(repo_path, str) and _REMOTE_REPO_MANAGER.is_git_url(repo_path):
        return _REMOTE_REPO_MANAGER.prepare_remote_repository(
            repo_url=repo_path,
            branch_name=branch_name,
            cache_dir=cache_dir,
        )
    return repo_path


def _apply_include_subpath(
    analysis_repo_path: Path | str,
    include_subpath: str | Path | None,
) -> Path | str:
    """
    Apply a repository-root-relative include subpath when configured.

    Args:
        analysis_repo_path (Path | str): Resolved repository root.
        include_subpath (str | Path | None): Optional include subpath.

    Returns:
        Path | str: Repository root or selected subpath.
    """
    if include_subpath in {None, ""}:
        return analysis_repo_path
    subpath = Path(include_subpath)
    if subpath == Path("."):
        return analysis_repo_path
    if subpath.is_absolute():
        raise ValueError("include_subpath must be repository-root-relative.")
    root = Path(analysis_repo_path).resolve()
    candidate = (root / subpath).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("include_subpath must resolve within repository root.")
    return candidate


def _create_analyzer(
    *,
    analysis_repo_path: Path | str,
    repo_ref: Path | str,
    branch_name: str,
    cache_dir: Path,
    output_dir: Path,
    since: datetime | None,
    until: datetime | None,
    authors: list[str] | None,
    languages: list[str] | None,
    exclude_dirs: list[Path] | None,
    show_progress: bool,
) -> GitRepoLOCAnalyzer:
    """
    Build a GitRepoLOCAnalyzer with common arguments.

    Returns:
        GitRepoLOCAnalyzer: Configured analyzer.
    """
    return GitRepoLOCAnalyzer(
        repo_path=analysis_repo_path,
        branch_name=branch_name,
        cache_dir=cache_dir,
        output_dir=output_dir,
        since=since,
        to=until,
        authors=authors,
        languages=languages,
        exclude_dirs=exclude_dirs,
        repo_ref=repo_ref,
        show_progress=show_progress,
    )


def _maybe_clear_cache(
    *,
    analyzer: GitRepoLOCAnalyzer,
    console: ColoredConsolePrinter | None,
    clear_cache: bool,
    show_progress: bool,
) -> None:
    """
    Clear cache files when requested.
    """
    if not clear_cache:
        return
    if show_progress and console is not None:
        console.print_h1("# Remove cache files.")
    analyzer.clear_cache_files()
    if show_progress and console is not None:
        console.print_ok(up=2, forward=50)


def _resolve_worker_count(workers: int | None, repo_count: int) -> int:
    """
    Resolve repository worker count based on CPU availability and repo count.

    Args:
        workers (int | None): Configured worker count.
        repo_count (int): Number of repositories to analyze.

    Returns:
        int: Effective worker count (minimum 1).
    """
    if repo_count <= 1:
        return 1
    cpu_count = os.cpu_count() or 1
    if workers is None:
        resolved = min(cpu_count, repo_count)
    else:
        resolved = min(workers, repo_count)
    return max(1, resolved)


def _analyze_single_repository(
    *,
    index: int,
    repo_path: Path | str,
    branch_name: str,
    exclude_dirs: list[Path] | None,
    include_subpath: str | Path | None,
    output_dir: Path,
    since: datetime | None,
    until: datetime | None,
    authors: list[str] | None,
    languages: list[str] | None,
    clear_cache: bool,
    show_progress: bool,
    progress_queue: object | None = None,
) -> tuple[int, str, pd.DataFrame, list[str]]:
    """
    Analyze a single repository and return its index, name, and LOC data.
    """
    if show_progress:
        os.environ.pop("ANALYZE_GIT_REPO_LOC_LOG_AUTH", None)
    else:
        os.environ["ANALYZE_GIT_REPO_LOC_LOG_AUTH"] = "0"
    console = ColoredConsolePrinter() if show_progress else None
    repository_name = GitRepoLOCAnalyzer.get_repository_name(repo_path)
    _emit_repo_progress(
        progress_queue,
        _REPO_EVENT_START,
        index,
        repository_name,
    )
    if show_progress and console is not None:
        console.print_h1("\n")
        console.print_h1(
            f"# Analysis of LOC in git repository: {repository_name} ({branch_name})",
        )
        if exclude_dirs is not None:
            console.print_h1(f"## Excluded directories:{exclude_dirs}")
    try:
        analysis_repo_path = _resolve_analysis_repo_path(
            repo_path=repo_path,
            branch_name=branch_name,
            cache_dir=output_dir / ".cache",
        )
        analysis_repo_path = _apply_include_subpath(
            analysis_repo_path,
            include_subpath,
        )

        analyzer = _create_analyzer(
            analysis_repo_path=analysis_repo_path,
            repo_ref=repo_path,
            branch_name=branch_name,
            cache_dir=output_dir / ".cache",
            output_dir=output_dir,
            since=since,
            until=until,
            authors=authors,
            languages=languages,
            exclude_dirs=exclude_dirs,
            show_progress=show_progress,
        )

        _maybe_clear_cache(
            analyzer=analyzer,
            console=console,
            clear_cache=clear_cache,
            show_progress=show_progress,
        )

        def progress_callback(kind: str, value: int) -> None:
            event_kind = _REPO_EVENT_ADVANCE
            if kind == "total":
                event_kind = _REPO_EVENT_TOTAL
            elif kind == "scan_total":
                event_kind = _REPO_EVENT_SCAN_TOTAL
            elif kind == "scan_advance":
                event_kind = _REPO_EVENT_SCAN_ADVANCE
            _emit_repo_progress(
                progress_queue,
                event_kind,
                index,
                repository_name,
                value,
            )

        loc_data = analyzer.get_commit_analysis(
            progress_callback=progress_callback if progress_queue is not None else None
        )
        analyzer.save_cache()

        repo_output_dir = _ensure_repo_output_dir(output_dir, repository_name)
        loc_data.to_csv(repo_output_dir / "loc_data.csv")

        return index, repository_name, loc_data, analyzer._warnings
    finally:
        _emit_repo_progress(
            progress_queue,
            _REPO_EVENT_FINISH,
            index,
            repository_name,
        )


def _ensure_repo_output_dir(output_dir: Path, repository_name: str) -> Path:
    """
    Ensure the output directory exists for a repository.

    Returns:
        Path: Created output directory.
    """
    repo_output_dir = output_dir / repository_name
    repo_output_dir.mkdir(parents=True, exist_ok=True)
    return repo_output_dir


def save_repository_branch_info(repo_paths, output_file: Path) -> None:
    """
    Saves the repository and branch information to a file.

    Args:
        repo_paths: The list of repository paths and branch names.
        output_file (Path): The path to the output file.

    Writes:
        A file named "repo_list.txt" in the specified `analysis_output_dir` containing
        the repository paths and branch names in the format:
        "repository: <repo_path>, branch: <branch_name>"
    """
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    f"repository: {entry[0]}, branch: {entry[1]}"
                    for entry in repo_paths
                ]
            )
        )


def analyze_trends(
    category_column: str,
    interval: str,
    loc_data: pd.DataFrame,
    analysis_data: pd.DataFrame,
    output_path: Path = None,
) -> pd.DataFrame:
    """
    Analyze the trends in the LOC data and save the results to a CSV file.

    Args:
        category_column (str): The column name in `loc_data` representing the category to group by.
        interval (str): The column name in `loc_data` representing the interval to group by.
        loc_data (pd.DataFrame): A DataFrame containing lines of code data with at least
                                 the columns specified by `category_column`, `interval`, and 'NLOC'.
        analysis_data (pd.DataFrame): A DataFrame containing the aggregated LOC data for each group.
                                      If None, the DataFrame will be created from scratch.
        output_path (Path): The path to save the output CSV file. If None, the file will not be saved.

    Returns:
        pd.DataFrame: A DataFrame containing the aggregated LOC data for each group.

    """
    aggregate_functions = {
        "Datetime": "min",
        "Repository": "first",
        "Branch": "first",
        "Commit_hash": "first",
        "Author": "first",
        "Language": "first",
        "NLOC_Added": "sum",
        "NLOC_Deleted": "sum",
        "NLOC": "sum",
    }
    # Remove the category column from the aggregate functions.
    # It will be used as the index in the groupby operation.
    aggregate_functions.pop(category_column, None)
    trends_data = (
        loc_data.groupby([interval, category_column])
        .agg(aggregate_functions)
        .reset_index()
    )
    trends_data.drop(columns=["Datetime", "Commit_hash"], inplace=True)

    if output_path is not None:
        output_prefix = category_column.lower()
        trends_data.to_csv(output_path / f"{output_prefix}_trends.csv", index=False)

    return pd.concat([analysis_data, trends_data], ignore_index=True)


def _resolve_exclude_dirs(
    args: argparse.Namespace, exclude_dirs: list[Path] | None
) -> list[Path] | None:
    """
    Resolve excluded directories, preferring CLI overrides when provided.
    """
    if args.exclude_dirs is not None:
        return args.exclude_dirs
    return exclude_dirs


def _unpack_repo_entry(
    repo_entry: tuple,
) -> tuple[Path | str, str, list[Path] | None, str | Path | None]:
    """
    Normalize repository entries to include optional include subpath.
    """
    if len(repo_entry) == 3:
        repo_path, branch_name, exclude_dirs = repo_entry
        return repo_path, branch_name, exclude_dirs, None
    if len(repo_entry) == 4:
        repo_path, branch_name, exclude_dirs, include_subpath = repo_entry
        return repo_path, branch_name, exclude_dirs, include_subpath
    raise ValueError("Repository entries must contain 3 or 4 values.")


def _analyze_repositories_sequential(
    *,
    args: argparse.Namespace,
    repo_entries: list[tuple[Path | str, str, list[Path] | None]],
    progress: tqdm,
    progress_queue: object | None = None,
    results: dict[int, pd.DataFrame],
    warnings: list[str],
) -> None:
    """
    Analyze repositories sequentially and update results in-place.
    """
    for index, repo_entry in enumerate(repo_entries):
        repo_path, branch_name, exclude_dirs, include_subpath = _unpack_repo_entry(
            repo_entry
        )
        resolved_excludes = _resolve_exclude_dirs(args, exclude_dirs)
        try:
            _, repository_name, loc_data, repo_warnings = _analyze_single_repository(
                index=index,
                repo_path=repo_path,
                branch_name=branch_name,
                exclude_dirs=resolved_excludes,
                include_subpath=include_subpath,
                output_dir=args.output,
                since=args.since,
                until=args.until,
                authors=args.author_name,
                languages=args.lang,
                clear_cache=args.clear_cache,
                show_progress=False,
                progress_queue=progress_queue,
            )
        except (OSError, ValueError) as ex:
            handle_exception(ex)
        warnings.extend(
            f"{repository_name}: {warning}" for warning in repo_warnings
        )
        results[index] = loc_data
        progress.update(1)


def _build_repo_progress_bars(
    repo_entries: list[tuple],
    *,
    progress: tqdm,
    label_width: int,
) -> tuple[dict[int, tqdm], dict[int, str]]:
    """
    Build child progress bars and labels for repository analysis.
    """
    repo_bars: dict[int, tqdm] = {}
    repo_labels: dict[int, str] = {}
    for index, repo_entry in enumerate(repo_entries):
        repo_path, _, _, _ = _unpack_repo_entry(repo_entry)
        repo_name = GitRepoLOCAnalyzer.get_repository_name(repo_path)
        label = _truncate_repo_label(repo_name, label_width)
        repo_labels[index] = label
        repo_bars[index] = tqdm(
            total=None,
            desc=f"Repo: {label} (queued)",
            position=progress.pos + 1 + index,
            leave=False,
            unit="commit",
        )
    return repo_bars, repo_labels


def _cleanup_repo_progress_listener(
    *,
    stop_event: Event,
    listener_thread: Thread,
    repo_bars: dict[int, tqdm],
    manager: SyncManager,
    progress_queue: object,
) -> None:
    """
    Stop the progress listener and clean up related resources.
    """
    stop_event.set()
    try:
        progress_queue.put((_REPO_EVENT_STOP, -1, "", 0))
    except (AttributeError, EOFError, OSError, ValueError):
        pass
    listener_thread.join()
    for bar in repo_bars.values():
        bar.close()
    manager.shutdown()


def _analyze_repositories_parallel(
    *,
    args: argparse.Namespace,
    repo_entries: list[tuple[Path | str, str, list[Path] | None]],
    worker_count: int,
    progress: tqdm,
    progress_queue: object | None = None,
    results: dict[int, pd.DataFrame],
    warnings: list[str],
) -> None:
    """
    Analyze repositories in parallel and update results in-place.
    """
    futures = []
    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        for index, repo_entry in enumerate(repo_entries):
            repo_path, branch_name, exclude_dirs, include_subpath = _unpack_repo_entry(
                repo_entry
            )
            resolved_excludes = _resolve_exclude_dirs(args, exclude_dirs)
            futures.append(
                executor.submit(
                    _analyze_single_repository,
                    index=index,
                    repo_path=repo_path,
                    branch_name=branch_name,
                    exclude_dirs=resolved_excludes,
                    include_subpath=include_subpath,
                    output_dir=args.output,
                    since=args.since,
                    until=args.until,
                    authors=args.author_name,
                    languages=args.lang,
                    clear_cache=args.clear_cache,
                    show_progress=False,
                    progress_queue=progress_queue,
                )
            )
        for future in as_completed(futures):
            try:
                index, repository_name, loc_data, repo_warnings = future.result()
            except (OSError, ValueError) as ex:
                handle_exception(ex)
            results[index] = loc_data
            warnings.extend(
                f"{repository_name}: {warning}" for warning in repo_warnings
            )
            progress.update(1)


def _print_repository_warnings(warnings: list[str]) -> None:
    """
    Print collected repository warnings after progress bars have completed.
    """
    if not warnings:
        return
    print(tr("warnings.title"), file=sys.stderr)
    for warning in warnings:
        print(f"- {warning}", file=sys.stderr)


def analyze_git_repositories(args: argparse.Namespace) -> list[pd.DataFrame]:
    """
    Analyze the LOC in the Git repositories.

    Args:
        args (argparse.Namespace): The command line arguments.

    Returns:
        list[pd.DataFrame]: The list of LOC dataframes for each repository.
    """
    # Analyze the LOC in the Git repositories
    loc_data_repositories: list[pd.DataFrame] = []
    repo_entries = list(args.repo_paths)
    repo_count = len(repo_entries)
    worker_count = _resolve_worker_count(args.workers, repo_count)
    results: dict[int, pd.DataFrame] = {}
    warnings: list[str] = []

    with tqdm(total=repo_count, desc="Analyzing repositories") as progress:
        manager: SyncManager | None = None
        progress_queue: object | None = None
        repo_bars: dict[int, tqdm] = {}
        stop_event: Event | None = None
        listener_thread: Thread | None = None
        try:
            if repo_count:
                manager = Manager()
                progress_queue = manager.Queue()
                repo_bars, repo_labels = _build_repo_progress_bars(
                    repo_entries,
                    progress=progress,
                    label_width=_REPO_PROGRESS_LABEL_WIDTH,
                )
                stop_event, listener_thread = _start_repo_progress_listener(
                    progress_queue=progress_queue,
                    repo_bars=repo_bars,
                    repo_labels=repo_labels,
                )
            if worker_count <= 1:
                _analyze_repositories_sequential(
                    args=args,
                    repo_entries=repo_entries,
                    progress=progress,
                    progress_queue=progress_queue,
                    results=results,
                    warnings=warnings,
                )
            else:
                _analyze_repositories_parallel(
                    args=args,
                    repo_entries=repo_entries,
                    worker_count=worker_count,
                    progress=progress,
                    progress_queue=progress_queue,
                    results=results,
                    warnings=warnings,
                )
        finally:
            if (
                manager is not None
                and progress_queue is not None
                and stop_event is not None
                and listener_thread is not None
            ):
                _cleanup_repo_progress_listener(
                    stop_event=stop_event,
                    listener_thread=listener_thread,
                    repo_bars=repo_bars,
                    manager=manager,
                    progress_queue=progress_queue,
                )

    _print_repository_warnings(warnings)

    for index in sorted(results.keys()):
        loc_data_repositories.append(results[index])

    return loc_data_repositories
