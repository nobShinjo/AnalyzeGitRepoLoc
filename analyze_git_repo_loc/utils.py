"""
This module provides utility functions for analyzing lines of code (LOC) in Git repositories.

Functions:
    parse_repos_paths(input_string: str) -> list[tuple[Path, str]]:
    parse_arguments(parser: argparse.ArgumentParser) -> argparse.Namespace:
        Parse command line arguments.
    handle_exception(ex: Exception) -> None:
    get_time_interval_and_period(interval: str) -> Union[str, str]:
    save_repository_branch_info(repo_paths, output_file: Path) -> None:
    analyze_trends(
    analyze_git_repositories(args: argparse.Namespace) -> list[pd.DataFrame]:
"""

import argparse
import sys
import traceback
from pathlib import Path
from typing import Union

import pandas as pd
from tqdm import tqdm

from analyze_git_repo_loc.colored_console_printer import ColoredConsolePrinter
from analyze_git_repo_loc.git_repo_loc_analyzer import GitRepoLOCAnalyzer


def parse_repos_paths(repo_paths_input: str) -> list[tuple[Path, str, list[Path]]]:
    """
    Parse repository paths, branches and excluded directories path from a string or file.

    Args:
        repo_paths_input (str): A string containing repository data or a path to a text file.
            Format for each line: "repo_path#branch,/path/to/exclude1,/path/to/exclude2,..."

    Returns:
       list[tuple[Path, str, list[Path]]]: A list of tuples containing:
        - Path: Repository path
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
        repo_path = Path(repo_and_branch[0].strip())
        branch_name = repo_and_branch[1].strip() if len(repo_and_branch) > 1 else "main"
        exclude_dirs = [Path(item.strip()) for item in parts[1:] if item.strip()]
        result.append((repo_path, branch_name, exclude_dirs))

    return result


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
        "repo_paths",
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

    parser.add_argument(
        "-o", "--output", type=Path, default="./out", help="Output path"
    )
    parser.add_argument("--since", type=str, default=None, help="Start Date yyyy-mm-dd")
    parser.add_argument("--until", type=str, default=None, help="End Date yyyy-mm-dd")
    parser.add_argument(
        "--interval",
        choices=["daily", "weekly", "monthly"],
        default="monthly",
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
        default=[],
        type=lambda s: [item.strip() for item in s.split(",")],
        help=(
            "Exclude directories from analysis, "
            "specified as comma-separated paths relative to the repository root."
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
    return parser.parse_args()


def handle_exception(ex: Exception) -> None:
    """
    Handle exceptions by printing the error message and exiting the program.

    Args:
        ex (Exception): The exception to handle.
    """
    print("An unexpected error occurred:", file=sys.stderr)
    print(f"Error type: {type(ex).__name__}", file=sys.stderr)
    print(f"Error message: {str(ex)}", file=sys.stderr)
    print("Stack trace:", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)


def get_time_interval_and_period(interval: str) -> Union[str, str]:
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
    # Initialize ColoredConsolePrinter
    console = ColoredConsolePrinter()

    # Analyze the LOC in the Git repositories
    loc_data_repositories: list[pd.DataFrame] = []
    for repo_path, branch_name, exclude_dirs in tqdm(
        args.repo_paths, desc="Analyzing repositories"
    ):
        exclude_dirs = exclude_dirs or args.exclude_dirs
        repository_name = GitRepoLOCAnalyzer.get_repository_name(repo_path)
        console.print_h1("\n")
        console.print_h1(
            f"# Analysis of LOC in git repository: {repository_name} ({branch_name})",
        )
        if exclude_dirs is not None:
            console.print_h1(f"## Excluded directories:{exclude_dirs}")

        # Create GitRepoLOCAnalyzer
        try:
            analyzer = GitRepoLOCAnalyzer(
                repo_path=repo_path,
                branch_name=branch_name,
                cache_dir=args.output / ".cache",
                output_dir=args.output,
                since=args.since,
                to=args.until,
                authors=args.author_name,
                languages=args.lang,
                exclude_dirs=exclude_dirs,
            )
        except OSError as ex:
            handle_exception(ex)

        # Remove cache files
        if args.clear_cache:
            console.print_h1("# Remove cache files.")
            try:
                analyzer.clear_cache_files()
                console.print_ok(up=2, forward=50)
            except FileNotFoundError as ex:
                handle_exception(ex)

        # Analyze the repository
        loc_data = analyzer.get_commit_analysis()

        # Save the analyzed data to pickle file (cache)
        try:
            analyzer.save_cache()
        except ValueError as ex:
            handle_exception(ex)

        # Create output directory for the repository
        repo_output_dir = args.output / repository_name
        try:
            repo_output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as ex:
            handle_exception(ex)
        # Save the LOC data
        loc_data.to_csv(repo_output_dir / "loc_data.csv")

        # append loc_data to loc_data_repositories
        loc_data_repositories.append(loc_data)

    return loc_data_repositories
