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
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Union
from urllib.parse import urlparse

import pandas as pd
from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo
from tqdm import tqdm

from analyze_git_repo_loc.colored_console_printer import ColoredConsolePrinter
from analyze_git_repo_loc.git_repo_loc_analyzer import GitRepoLOCAnalyzer


class RemoteAuthError(ValueError):
    """Authentication failed while accessing a remote repository."""


def _is_git_url(value: str) -> bool:
    """
    Detect whether a string is a git URL.

    Args:
        value (str): The input string to inspect.

    Returns:
        bool: True if the input looks like a git URL.
    """
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https", "ssh", "git"}:
        return True
    return value.startswith("git@") and ":" in value


def _parse_repo_identity(repo_url: str) -> tuple[str, str] | None:
    """
    Normalize a repository URL into a comparable (host, path) identity.

    Args:
        repo_url (str): Repository URL to normalize.

    Returns:
        tuple[str, str] | None: Normalized identity for comparison.
    """
    if repo_url.startswith("git@"):
        host_path = repo_url.split("@", 1)[-1]
        if ":" not in host_path:
            return None
        host, path = host_path.split(":", 1)
        return host.lower(), path.lstrip("/")
    parsed = urlparse(repo_url)
    if parsed.hostname and parsed.path:
        return parsed.hostname.lower(), parsed.path.lstrip("/")
    return None


def _get_token_for_host(host: str | None) -> tuple[str, str] | None:
    """
    Resolve a Git hosting token and username based on the host name.

    Args:
        host (str | None): Host name from the repository URL.

    Returns:
        tuple[str, str] | None: (token, username) pair when configured.
    """
    if not host:
        return None
    normalized = host.lower()
    if "github" in normalized:
        token = os.getenv("GITHUB_TOKEN")
        if token:
            return token, "x-access-token"
    if "gitlab" in normalized:
        token = os.getenv("GITLAB_TOKEN")
        if token:
            return token, "oauth2"
    return None


def _build_https_token_url(repo_url: str) -> str | None:
    """
    Build an HTTPS URL embedding a token for authentication.

    Args:
        repo_url (str): Repository URL.

    Returns:
        str | None: Token-authenticated URL when a token is available.
    """
    parsed = urlparse(repo_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    token_info = _get_token_for_host(parsed.hostname)
    if token_info is None:
        return None
    token, username = token_info
    netloc = f"{username}:{token}@{parsed.hostname}"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return parsed._replace(netloc=netloc).geturl()


def _strip_credentials(repo_url: str) -> str:
    """
    Remove embedded credentials from an HTTPS URL.

    Args:
        repo_url (str): Repository URL.

    Returns:
        str: Sanitized URL without user info.
    """
    parsed = urlparse(repo_url)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        netloc = parsed.hostname
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return parsed._replace(netloc=netloc).geturl()
    return repo_url


def _build_auth_candidates(repo_url: str) -> list[str]:
    """
    Build ordered clone/fetch URLs based on the provided scheme.

    Args:
        repo_url (str): Repository URL.

    Returns:
        list[str]: Ordered list of URLs to try.
    """
    parsed = urlparse(repo_url)
    candidates: list[str] = []
    if repo_url.startswith("git@") or parsed.scheme in {"ssh", "git"}:
        candidates.append(repo_url)
    elif parsed.scheme in {"http", "https"}:
        token_url = _build_https_token_url(repo_url)
        if token_url:
            candidates.append(token_url)
        candidates.append(repo_url)
    else:
        candidates.append(repo_url)

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            unique.append(candidate)
            seen.add(candidate)
    return unique


def _describe_auth_method(candidate: str) -> str:
    """
    Describe the authentication method implied by a clone/fetch URL.

    Args:
        candidate (str): Clone/fetch URL used for authentication.

    Returns:
        str: Human-readable authentication method label.
    """
    if candidate.startswith("git@"):
        return "SSH"
    parsed = urlparse(candidate)
    if parsed.scheme in {"ssh", "git"}:
        return "SSH"
    if parsed.scheme in {"http", "https"}:
        return "HTTPS"
    return "Unknown"


def _log_auth_success(repo_url: str, candidate: str) -> None:
    """
    Log the authentication method used to access a remote repository.

    Args:
        repo_url (str): Original repository URL.
        candidate (str): Clone/fetch URL that succeeded.
    """
    sanitized = _strip_credentials(candidate)
    method = _describe_auth_method(candidate)
    tqdm.write(f"Authentication succeeded: {method} ({sanitized})")


def _raise_auth_failure(repo_url: str, error: GitCommandError) -> None:
    """
    Raise a friendly authentication error for a remote repository.

    Args:
        repo_url (str): Repository URL.
        error (GitCommandError): Underlying Git error.
    """
    parsed = urlparse(repo_url)
    if repo_url.startswith("git@") or parsed.scheme in {"ssh", "git"}:
        hint = "Ensure your SSH keys have access to the repository."
    elif parsed.scheme in {"http", "https"}:
        hint = (
            "For private repositories, set GITHUB_TOKEN or GITLAB_TOKEN, "
            "or use an SSH URL."
        )
    else:
        hint = "Provide valid credentials for the repository URL and retry."
    message = f"Authentication failed for '{repo_url}'. {hint}"
    raise RemoteAuthError(message) from error


def _is_auth_failure(error: GitCommandError) -> bool:
    """
    Check whether a Git error looks like an authentication failure.

    Args:
        error (GitCommandError): Git error to inspect.

    Returns:
        bool: True when the error indicates authentication failure.
    """
    stderr = (error.stderr or "").lower()
    return any(
        phrase in stderr
        for phrase in (
            "authentication failed",
            "invalid username or token",
            "password authentication is not supported",
            "could not read username",
            "permission denied (publickey)",
        )
    )


def _ensure_origin_matches(repo: Repo, repo_url: str) -> None:
    """
    Validate that the cached repository origin matches the requested repository.

    Args:
        repo (Repo): Cached repository.
        repo_url (str): Requested repository URL.

    Raises:
        ValueError: If the cached repository points to a different origin.
    """
    origin_url = repo.remotes.origin.url if repo.remotes else None
    if origin_url is None:
        return
    origin_identity = _parse_repo_identity(origin_url)
    requested_identity = _parse_repo_identity(repo_url)
    if origin_identity and requested_identity and origin_identity != requested_identity:
        raise ValueError(
            f"Cached repository at {repo.working_tree_dir} does not match {repo_url}."
        )


def _fetch_with_auth(repo: Repo, repo_url: str) -> None:
    """
    Fetch updates using SSH first, with HTTPS token fallback when configured.

    Args:
        repo (Repo): Cached repository.
        repo_url (str): Requested repository URL.
    """
    origin = repo.remotes.origin if repo.remotes else None
    if origin is None:
        origin = repo.create_remote("origin", _strip_credentials(repo_url))
    original_url = origin.url
    last_error: GitCommandError | None = None
    for candidate in _build_auth_candidates(repo_url):
        try:
            if origin.url != candidate:
                origin.set_url(candidate)
            repo.git.fetch("--all", "--prune")
            _log_auth_success(repo_url, candidate)
            return
        except GitCommandError as ex:
            last_error = ex
        finally:
            if origin.url != original_url:
                origin.set_url(original_url)
    if last_error is not None:
        if _is_auth_failure(last_error):
            _raise_auth_failure(repo_url, last_error)
        raise last_error


def _clone_with_auth(repo_url: str, repo_path: Path) -> Repo:
    """
    Clone a repository using SSH first and HTTPS token fallback.

    Args:
        repo_url (str): Requested repository URL.
        repo_path (Path): Local clone path.

    Returns:
        Repo: Cloned repository.
    """
    last_error: GitCommandError | None = None
    for candidate in _build_auth_candidates(repo_url):
        try:
            repo = Repo.clone_from(candidate, repo_path)
            sanitized_candidate = _strip_credentials(candidate)
            if repo.remotes and repo.remotes.origin.url != sanitized_candidate:
                repo.remotes.origin.set_url(sanitized_candidate)
            _log_auth_success(repo_url, candidate)
            return repo
        except GitCommandError as ex:
            last_error = ex
            if repo_path.exists():
                shutil.rmtree(repo_path)
    if last_error is not None:
        if _is_auth_failure(last_error):
            _raise_auth_failure(repo_url, last_error)
        raise last_error
    raise ValueError("No authentication candidates available for clone.")


def _get_remote_cache_path(cache_dir: Path, repo_url: str) -> Path:
    """
    Build a cache directory path for a remote repository clone.

    Args:
        cache_dir (Path): Base cache directory.
        repo_url (str): Remote repository URL.

    Returns:
        Path: Path to the cached clone.
    """
    repo_name = GitRepoLOCAnalyzer.get_repository_name(repo_url)
    return cache_dir / "remote-repos" / repo_name


def _checkout_branch(repo: Repo, branch_name: str) -> None:
    """
    Ensure the target branch is checked out.

    Args:
        repo (Repo): GitPython repository instance.
        branch_name (str): Branch to check out.

    Raises:
        ValueError: If the branch does not exist.
    """
    if branch_name in repo.heads:
        repo.git.checkout(branch_name)
        return
    remote_ref = f"origin/{branch_name}"
    remote_refs = [ref.name for ref in repo.remotes.origin.refs]
    if remote_ref in remote_refs:
        repo.git.checkout("-B", branch_name, remote_ref)
        return
    raise ValueError(f"Branch '{branch_name}' not found in remote repository.")


def _prepare_remote_repository(
    repo_url: str, branch_name: str, cache_dir: Path
) -> Path:
    """
    Clone or update a remote repository in the local cache.

    Args:
        repo_url (str): Remote repository URL.
        branch_name (str): Branch to check out.
        cache_dir (Path): Base cache directory for clones.

    Returns:
        Path: Local path to the cached clone.
    """
    repo_path = _get_remote_cache_path(cache_dir, repo_url)
    try:
        repo = Repo(repo_path)
        _ensure_origin_matches(repo, repo_url)
        _fetch_with_auth(repo, repo_url)
    except (InvalidGitRepositoryError, NoSuchPathError):
        if repo_path.exists():
            shutil.rmtree(repo_path)
        repo_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            repo = _clone_with_auth(repo_url, repo_path)
        except GitCommandError as ex:
            raise ValueError(f"Failed to clone remote repository: {ex}") from ex
    except GitCommandError as ex:
        raise ValueError(f"Failed to update remote repository: {ex}") from ex
    _checkout_branch(repo, branch_name)
    return repo_path


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
        repo_path = raw_repo if _is_git_url(raw_repo) else Path(raw_repo)
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
        values (list[str] | None): The list input to normalize.

    Returns:
        list[str] | None: Normalized items or None when unset/empty.
    """
    if values is None:
        return None
    normalized = [item.strip() for item in values if item and item.strip()]
    return normalized or None


def _parse_optional_iso_date(value: str | None, label: str) -> datetime | None:
    """
    Parse an optional ISO date string into a datetime object.

    Args:
        value (str | None): The raw CLI input.
    Returns:
        datetime | None: Parsed datetime or None when unset/empty.

    Raises:
        ValueError: If the date format is invalid.
    """
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
        default=None,
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
    args = parser.parse_args()
    try:
        args.since = _parse_optional_iso_date(args.since, "--since")
        args.until = _parse_optional_iso_date(args.until, "--until")
        args.lang = _normalize_optional_list(args.lang)
        args.author_name = _normalize_optional_list(args.author_name)
        args.exclude_dirs = _normalize_optional_list(args.exclude_dirs)
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
        analysis_repo_path = repo_path
        if isinstance(repo_path, str) and _is_git_url(repo_path):
            try:
                analysis_repo_path = _prepare_remote_repository(
                    repo_url=repo_path,
                    branch_name=branch_name,
                    cache_dir=args.output / ".cache",
                )
            except (OSError, ValueError) as ex:
                handle_exception(ex)
        console.print_h1("\n")
        console.print_h1(
            f"# Analysis of LOC in git repository: {repository_name} ({branch_name})",
        )
        if exclude_dirs is not None:
            console.print_h1(f"## Excluded directories:{exclude_dirs}")

        # Create GitRepoLOCAnalyzer
        try:
            analyzer = GitRepoLOCAnalyzer(
                repo_path=analysis_repo_path,
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
