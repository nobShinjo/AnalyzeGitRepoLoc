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
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from analyze_git_repo_loc.colored_console_printer import ColoredConsolePrinter
from analyze_git_repo_loc.git_repo_loc_analyzer import GitRepoLOCAnalyzer
from analyze_git_repo_loc.remote_auth import RemoteAuthError
from analyze_git_repo_loc.remote_repos import RemoteRepoManager
from analyze_git_repo_loc.yaml_config import merge_yaml_config

_REMOTE_REPO_MANAGER = RemoteRepoManager()


def parse_repos_paths(
    repo_paths_input: str,
) -> list[tuple[Path | str, str, list[Path]]]:
    """
    Parse repository paths, branches and excluded directories path from a string or file.

    Args:
        repo_paths_input (str): A string containing repository data or a path to a text file.
            Format for each line: "repo_path#branch,/path/to/exclude1,/path/to/exclude2,..."

    Returns:
       list[tuple[Path | str, str, list[Path]]]: A list of tuples containing:
        - Path | str: Repository path (local path or remote URL)
        - str: Branch name
        - list[Path]: Excluded directories paths
    """
    path = Path(repo_paths_input)
    repo_entries = []

    if path.is_file():
        try:
            # If the input string is a file, read its contents
            with open(path, "r", encoding="utf-8") as f:
                repo_entries = f.read().strip().splitlines()
        except OSError as ex:
            handle_exception(ex)

        if not repo_entries:
            handle_exception(ValueError("The file is empty."))
    else:
        # Otherwise, treat the string as a list of repo paths
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

    # pylint: enable=line-too-long
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="YAML configuration file path",
    )

    parser.add_argument(
        "repo_paths",
        nargs="?",
        type=parse_repos_paths,
        help=(
            "A text file containing a list of repositories, "
            "or a comma-separated list of Git repository paths or URLs,\n"
            "optionally followed by a branch name separated with '#'.\n"
            "Examples: /path/to/repo1#branch-name or"
            "http://github.com/user/repo2.git#branch-name.\n"
            "If no branch is specified, 'main' will be used as the default."
        ),
    )

    parser.add_argument("-o", "--output", type=Path, default=None, help="Output path")
    parser.add_argument("--since", type=str, default=None, help="Start Date yyyy-mm-dd")
    parser.add_argument("--until", type=str, default=None, help="End Date yyyy-mm-dd")
    parser.add_argument(
        "--interval",
        choices=["daily", "weekly", "monthly"],
        default=None,
        help="Interval (default: monthly)",
    )
    parser.add_argument(
        "--lang",
        type=lambda s: [item.strip() for item in s.split(",")],
        default=None,
        help="Count only the given space separated, case-insensitive languages L1,L2,L3, etc. ",
    )
    parser.add_argument(
        "--author-name",
        type=lambda s: [item.strip() for item in s.split(",")],
        default=None,
        help="Author name or comma-separated list of author names to filter commits",
    )
    parser.add_argument(
        "--exclude-dirs",
        default=None,
        type=lambda s: [item.strip() for item in s.split(",")],
        help=(
            "Exclude directories from analysis, "
            "specified as comma-separated paths relative to the repository root."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            "Maximum number of repositories to analyze concurrently "
            "(default: auto)."
        ),
    )

    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="If set, the cache will be cleared before executing the main function.",
    )
    parser.add_argument(
        "--no-plot-show",
        action="store_true",
        help="If set, the plots will not be shown.",
    )
    args = parser.parse_args()
    try:
        if args.config is not None:
            args = merge_yaml_config(
                args=args,
                repo_manager=_REMOTE_REPO_MANAGER,
                normalize_list=_normalize_optional_list,
            )
        else:
            if args.repo_paths is None:
                raise ValueError(
                    "repo_paths is required when --config is not provided."
                )
            if args.output is None:
                args.output = Path("./out")
            if args.interval is None:
                args.interval = "monthly"
        args.since = _parse_optional_iso_date(args.since, "--since")
        args.until = _parse_optional_iso_date(args.until, "--until")
        args.lang = _normalize_optional_list(args.lang)
        args.author_name = _normalize_optional_list(args.author_name)
        args.exclude_dirs = _normalize_optional_list(args.exclude_dirs)
        args.workers = _normalize_optional_int(args.workers, "--workers")
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
    print("An unexpected error occurred:", file=sys.stderr)
    print(f"Error type: {type(ex).__name__}", file=sys.stderr)
    print(f"Error message: {str(ex)}", file=sys.stderr)
    print("Stack trace:", file=sys.stderr)
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
    output_dir: Path,
    since: datetime | None,
    until: datetime | None,
    authors: list[str] | None,
    languages: list[str] | None,
    clear_cache: bool,
    show_progress: bool,
) -> tuple[int, str, pd.DataFrame]:
    """
    Analyze a single repository and return its index, name, and LOC data.
    """
    console = ColoredConsolePrinter() if show_progress else None
    repository_name = GitRepoLOCAnalyzer.get_repository_name(repo_path)
    if show_progress and console is not None:
        console.print_h1("\n")
        console.print_h1(
            f"# Analysis of LOC in git repository: {repository_name} ({branch_name})",
        )
        if exclude_dirs is not None:
            console.print_h1(f"## Excluded directories:{exclude_dirs}")

    analysis_repo_path = _resolve_analysis_repo_path(
        repo_path=repo_path,
        branch_name=branch_name,
        cache_dir=output_dir / ".cache",
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

    loc_data = analyzer.get_commit_analysis()
    analyzer.save_cache()

    repo_output_dir = _ensure_repo_output_dir(output_dir, repository_name)
    loc_data.to_csv(repo_output_dir / "loc_data.csv")

    return index, repository_name, loc_data


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
                    f"repository: {repo_path}, branch: {branch_name}"
                    for repo_path, branch_name, _ in repo_paths
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

    with tqdm(total=repo_count, desc="Analyzing repositories") as progress:
        if worker_count <= 1:
            for index, (repo_path, branch_name, exclude_dirs) in enumerate(
                repo_entries
            ):
                exclude_dirs = (
                    args.exclude_dirs
                    if args.exclude_dirs is not None
                    else exclude_dirs
                )
                try:
                    _, _, loc_data = _analyze_single_repository(
                        index=index,
                        repo_path=repo_path,
                        branch_name=branch_name,
                        exclude_dirs=exclude_dirs,
                        output_dir=args.output,
                        since=args.since,
                        until=args.until,
                        authors=args.author_name,
                        languages=args.lang,
                        clear_cache=args.clear_cache,
                        show_progress=True,
                    )
                except (OSError, ValueError, FileNotFoundError) as ex:
                    handle_exception(ex)
                results[index] = loc_data
                progress.update(1)
        else:
            from concurrent.futures import ProcessPoolExecutor, as_completed

            futures = []
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                for index, (repo_path, branch_name, exclude_dirs) in enumerate(
                    repo_entries
                ):
                    exclude_dirs = (
                        args.exclude_dirs
                        if args.exclude_dirs is not None
                        else exclude_dirs
                    )
                    futures.append(
                        executor.submit(
                            _analyze_single_repository,
                            index=index,
                            repo_path=repo_path,
                            branch_name=branch_name,
                            exclude_dirs=exclude_dirs,
                            output_dir=args.output,
                            since=args.since,
                            until=args.until,
                            authors=args.author_name,
                            languages=args.lang,
                            clear_cache=args.clear_cache,
                            show_progress=False,
                        )
                    )
                for future in as_completed(futures):
                    try:
                        index, repository_name, loc_data = future.result()
                    except (OSError, ValueError, FileNotFoundError) as ex:
                        handle_exception(ex)
                    results[index] = loc_data
                    tqdm.write(f"Completed repository analysis: {repository_name}")
                    progress.update(1)

    for index in sorted(results.keys()):
        loc_data_repositories.append(results[index])

    return loc_data_repositories
