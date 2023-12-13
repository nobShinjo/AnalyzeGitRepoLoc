"""
Analyze Git repositories and visualize code LOC.

"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
from git import Commit, InvalidGitRepositoryError, NoSuchPathError, Repo
from plotly.subplots import make_subplots
from tqdm import tqdm

# Global variables
CURRENT_PATH: str = os.getcwd()


def get_commits(
    repo_path: Path,
    branch: str,
    start_date: datetime,
    end_date: datetime,
    interval="daily",
) -> list[Commit]:
    """
    get_commits Get a list of Commit object.

    This function retrieves a list of commits for a specified repository and branch.
    It filters for a specified date range and interval.

    Args:
        repo_path (Path): The file system path to the Git repository.
        branch (str): The name of the branch to retrieve commits from.
        start_date (datetime): The start date for filtering commits.
        end_date (datetime): The end date for filtering commits.
        interval (str, optional): The interval to use for filtering commits. Defaults to 'daily'.

    Raises:
        ValueError: If the provided `interval` is not one of 'daily', 'weekly', or 'monthly'.

    Returns:
        list[Commit]: A list of commit object.
    """

    # Initialize the repository object
    try:
        repo = Repo(repo_path)
    except InvalidGitRepositoryError as e:
        print(
            f"InvalidGitRepositoryError: Not a git repository. {str(e)}",
            file=sys.stderr,
        )
        sys.exit(1)
    except NoSuchPathError as e:
        print(f"NoSuchPathError: No such path. {str(e)}", file=sys.stderr)
        sys.exit(1)

    # Set the timedelta object that defines the interval.
    # NOTE: Approximate average length of month in days
    intervals = {
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(days=30),
    }
    delta = intervals.get(interval)
    if not delta:
        raise ValueError("Invalid interval. Choose 'daily', 'weekly', or 'monthly'.")

    # Start and end dates to filter
    since = f'--since="{start_date.strftime("%Y-%m-%d")}"'
    until = f'--until="{end_date.strftime("%Y-%m-%d")}"'

    # Search and filter commits in order and add them to the list
    # NOTE: Commit dates are ordered by newest to oldest, so filter by end date
    last_added_commit_date = end_date
    commits: list[Commit] = []
    for commit in repo.iter_commits(branch, since=since, until=until):
        commit_date = datetime.fromtimestamp(commit.committed_date)
        if commit_date <= last_added_commit_date - delta:
            # commits.append((commit.hexsha, commit_date.strftime("%Y-%m-%d %H:%M:%S")))
            commits.append(commit)
            last_added_commit_date = commit_date

    return commits


def run_cloc(commit: Commit, lang: list[str] = None) -> str:
    """
    Run the `cloc` to analyze LOC for a specific commit in a Git repository.

    This function executes the `cloc` program with JSON output format, targeting
    the provided commit. `cloc` is a command line tool used to count blank lines,
    comment lines, and physical lines of source code in many programming languages.

    Args:
        commit (Commit): A GitPython `Commit` object representing the commit to analyze.
        lang (list[str], optional): List of languages to search. Defaults to 'None'.

    Returns:
        str: A JSON-formatted string containing the `cloc` analysis result.

    Remarks:
        The command executed is equivalent to:
            cloc --json --quiet --git --include-lang=L1, L2, L3 <commit hash>
        and produces output in the following format:
            {
                "Language": {
                    "nfiles": count,
                    "blank": count,
                    "comment": count,
                    "code": count
                },
                ...
            }

    Raises:
        subprocess.CalledProcessError: If the `cloc` command fails to execute properly.
        SystemExit: If there is an error during the execution of the `cloc` command.
    """

    # Generate argument options for the language list to be searched
    if lang is None:
        include_lang: str = ""
    else:
        include_lang: str = "--include-lang=" + ",".join(lang)

    try:
        # Run cloc.exe and analyze LOC
        result = subprocess.run(
            [
                "cloc.exe",
                "--json",
                "--quiet",
                "--git",
                include_lang,
                commit.hexsha,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        # if result.stdout:
        #     print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

    return result.stdout


def plot_data(monthly_data: pd.DataFrame, output_path: str):
    """
    plot_data グラフを表示, 保存する

    Args:
        monthly_data (DataFrame): 各月のLOC数データ
        output_path (str): ファイル出力先
    """

    grouped_data = monthly_data.groupby(["month", "language"]).sum().reset_index()
    language_data = grouped_data.pivot(index="month", columns="language", values="code")
    sum_data = language_data.pop("SUM")

    # 言語別統計
    fig_lang = px.area(data_frame=language_data, color="language")
    fig_lang_traces = []
    for trace in range(len(fig_lang["data"])):
        fig_lang_traces.append(fig_lang["data"][trace])

    # 合計LOC
    fig_sum = px.line(data_frame=sum_data)
    fig_sum_traces = []
    for trace in range(len(fig_sum["data"])):
        fig_sum["data"][trace]["showlegend"] = False
        fig_sum_traces.append(fig_sum["data"][trace])

    fig = make_subplots(
        rows=1,
        cols=1,
        x_title="Month",
        y_title="LOC",
    )
    fig.update_layout(
        title={"text": "LOC by Language / Month", "x": 0.5, "xanchor": "center"}
    )

    for traces in fig_lang_traces:
        fig.append_trace(traces, row=1, col=1)
    for traces in fig_sum_traces:
        fig.append_trace(traces, row=1, col=1)
    fig.show()
    fig.write_html(os.path.join(output_path, "report.html"))


def analyze_git_repo_loc(
    repo_path: Path,
    branch: str,
    start_date_str: str,
    end_date_str: str,
    interval: str = "daily",
    lang: list = None,
) -> pd.DataFrame:
    """
    analyze_git_repo_loc Analyze and extract LOC statistics from a Git repository.

    Specified repository path, branch name, date range, and an optional interval, this function
    extracts the counts of lines of code, including the number of files, comments, blank,
    and lines of code per language. It runs `cloc` for each commit within the specfied range
    and compiles the results into a single DataFrame.

    Args:
        repo_path (Path): The file system path to the Git repository.
        branch (str): The name of the branch to retrieve commits from.
        start_date_str (str): The start date for filtering commits in 'YYYY-MM-DD' format.
        end_date_str (str): The end date for filtering commits in 'YYYY-MM-DD' format.
        interval (str, optional): The Interval to filter LOC ("hourly", "daily", "weekly", etc.).
                                  Defaults to 'daily'.
        lang (list[str], optional): List of languages to search. Defaults to 'None'

    Returns:
        pd.DataFrame: A DataFrame containing the analysis results with columns for Commit hash,
                      Date, Language, Number of files, Comments, Blank lines, and Code lines.

    Raises:
        ValueError: If the provided start or end date strings are not in the correct format
                    or represent invalid dates.
        SystemExit: If failing to parse the start or end date strings.
    """

    # Define start and end dates as datetime type.
    try:
        if start_date_str is None:
            start_date: datetime = datetime.strptime("1970-01-01", "%Y-%m-%d")
        else:
            start_date: datetime = datetime.strptime(start_date_str, "%Y-%m-%d")

        if end_date_str is None:
            end_date: datetime = datetime.now()
        else:
            end_date: datetime = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # Get a list of Commits filtered by the specified date and interval.
    try:
        commits = get_commits(
            repo_path=repo_path,
            branch=branch,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

    cloc_df: pd.DataFrame = pd.DataFrame(
        columns=[
            "Commit",
            "Date",
            "Language",
            "nFiles",
            "comment",
            "blank",
            "code",
        ],
    )

    # Memorize current directory
    current_path: Path = Path().resolve()
    # Change the directory to the repository path.
    os.chdir(repo_path)

    # Analyse LOC for each commit.
    for commit in tqdm(commits):
        result = run_cloc(commit=commit, lang=lang)
        df = convert_json_to_dataframe(result)

        # Insert Commit and Date columns at the head of columns in the dataframe.
        df.insert(0, "Commit", commit.hexsha)
        committed_date = datetime.fromtimestamp(commit.committed_date)
        df.insert(1, "Date", committed_date.strftime("%Y-%m-%d %H:%M:%S"))

        # Concatenate data frames
        cloc_df = pd.concat([cloc_df, df])

    cloc_df.reset_index(inplace=True, drop=True)

    # Return to original directory.
    os.chdir(current_path)

    return cloc_df


def convert_json_to_dataframe(json_str):
    """
    Convert a JSON string to a pandas DataFrame after removing specified keys.

    This function takes a JSON string and decodes it into a dictionary, removes
    the 'header' and 'SUM' elements if they exist, and then converts it into a
    pandas DataFrame. The index of the DataFrame is reset, and the first column
    is renamed to 'Language'.

    Args:
        json_str (str): A JSON string representation of the data to be converted into a DataFrame.

    Returns:
    df : pandas.DataFrame
        The resulting pandas DataFrame with the 'header' and 'SUM' entries removed,
        and the 'index' column renamed to 'Language'.
    """

    # Decode json string to dict type
    json_dict = json.loads(json_str)
    json_dict.pop("header", None)
    json_dict.pop("SUM", None)

    # Create a dataframe from the json dict type.
    df = pd.DataFrame.from_dict(json_dict, orient="index")
    df.reset_index(inplace=True)
    df.rename(columns={"index": "Language"}, inplace=True)

    return df


def check_cloc_path() -> None:
    """
    check_cloc_path Checks the presence of `cloc.exe` in the system's PATH or current directory.

    This function attempts to run `cloc.exe --version` to determine if 'cloc.exe' is installed
    and accessible. If the execution is successful, it prints out the version of 'cloc.exe'.
    If 'cloc.exe' is not found, the function prints an error message and exits.

    Raises:
        FileNotFoundError: If `cloc.exe` is not found on the system's PATH or current directory.
    """
    try:
        version_result = subprocess.run(
            [
                "cloc.exe",
                "--version",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"cloc.exe: Ver. {version_result.stdout}")
    except FileNotFoundError as e:
        print(
            f"Error: Not found cloc.exe. {str(e)}",
            file=sys.stderr,
        )
        sys.exit(1)


def make_output_dir(output_path: str):
    """
    make_output_dir Make output directory

    Args:
        output_path (str): Output directory name

    Returns:
        _type_: Full path of output directory
    """
    output_full_path: str = os.path.join(
        os.getcwd().replace(os.sep, "/"), output_path
    ).replace(os.sep, "/")
    if not os.path.exists(output_full_path):
        os.makedirs(output_full_path, exist_ok=True)
    return output_full_path


if __name__ == "__main__":
    # Parsing command line arguments
    parser = argparse.ArgumentParser(
        prog="analyze_git_repo_loc",
        description="Analyze Git repositories and visualize code LOC.",
    )
    # pylint: enable=line-too-long
    parser.add_argument(
        "repo_path",
        type=Path,
        help="Path of Git repository",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default="./out", help="Output path"
    )
    parser.add_argument(
        "-s", "--start_date", type=str, default=None, help="Start Date yyyy-mm-dd"
    )
    parser.add_argument(
        "-e", "--end_date", type=str, default=None, help="End Date yyyy-mm-dd"
    )
    parser.add_argument(
        "-b", "--branch", type=str, default="main", help="Branch name (default: main)"
    )
    parser.add_argument(
        "--interval",
        choices=["daily", "weekly", "monthly"],
        default="monthly",
        help="Interval (default: monthly)",
    )
    parser.add_argument(
        "--lang",
        nargs="+",
        type=str,
        default=None,
        help="Count only the given space separated, case-insensitive languages L1 L2 L3 etc. \n \
        Use 'cloc --show-lang' to see the list of recognized languages.",
    )
    args = parser.parse_args()

    # Make output directory
    output_dir = make_output_dir(args.output)

    # Check cloc.exe path
    check_cloc_path()

    # Analyze LOC against the git repository
    loc_data: pd.DataFrame = analyze_git_repo_loc(
        repo_path=args.repo_path,
        branch=args.branch,
        start_date_str=args.start_date,
        end_date_str=args.end_date,
        interval=args.interval,
    )
    # Save to csv file.
    loc_data.to_csv(output_dir + "/loc_data.csv")
    # Create charts
    plot_data(monthly_data=loc_data, output_path=output_dir)
