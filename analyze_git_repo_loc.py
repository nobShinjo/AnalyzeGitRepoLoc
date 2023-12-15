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

import colorama
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from colorama import Cursor, Fore, Style
from git import Commit, InvalidGitRepositoryError, NoSuchPathError, Repo
from plotly.subplots import make_subplots
from tqdm import tqdm

# Global variables
cloc_path: Path = None
""" The file system path to 'cloc.exe' """


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

    print(f"-> {len(commits)} commits found.", end=os.linesep + os.linesep)
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
                str(cloc_path.resolve()),
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


def plot_data(trend_data: pd.DataFrame, sum_data: pd.DataFrame) -> go.Figure:
    """
    Plot the trend of lines of code (LOC) over time by language and the total LOC.

    This function creates a subplot figure with an area plot to represent the LOC trend by language
    and overlays line plots representing the total LOC.
    The resulting plot is displayed using Plotly.

    Args:
        trend_data (pd.DataFrame): A DataFrame containing the trend data of LOC by language.
        sum_data (pd.DataFrame): A DataFrame containing the summarized trend data of total LOC.

    Returns:
        go.Figure : The final Plotly figure object that contains the combined area and line plot.

    Examples:
    >>> trend_data = pd.DataFrame({
    ...     "Date": pd.to_datetime(["2021-01-01", "2021-02-01", "2021-03-01"]),
    ...     "Language": ["Python", "Python", "Python"],
    ...     "LOC": [100, 200, 300],
    ... })
    >>> sum_data = pd.DataFrame({
    ...     "Date": pd.to_datetime(["2021-01-01", "2021-02-01", "2021-03-01"]),
    ...     "Total_LOC": [1000, 1500, 1800],
    ... })
    >>> fig = plot_data(trend_data, sum_data)

    Notes:
        Both `trend_data` and `sum_data` should have a 'Date' field for the plots to align properly
        on the x-axis.
    """

    # Field area plot of LOC trend by language
    fig_lang = px.area(data_frame=trend_data, color="Language", line_shape=None)
    fig_lang_traces = []
    for trace in range(len(fig_lang["data"])):
        fig_lang_traces.append(fig_lang["data"][trace])

    # Line plots of total LOC trend
    fig_sum = px.line(data_frame=sum_data, markers=True)
    fig_sum_traces = []
    for trace in range(len(fig_sum["data"])):
        fig_sum["data"][trace]["showlegend"] = False
        fig_sum_traces.append(fig_sum["data"][trace])

    fig: go.Figure = make_subplots(
        rows=1,
        cols=1,
        x_title="Date",
        y_title="LOC",
    )
    fig.update_xaxes(
        showline=True,
        linewidth=1,
        linecolor="grey",
        color="black",
        gridcolor="lightgrey",
        gridwidth=0.5,
        title_font_size=18,
        title_standoff=50,
        tickangle=-45,
        tickformat="'%y-%m",
        tickfont_size=10,
        automargin=True,
    )
    fig.update_yaxes(
        showline=True,
        linewidth=1,
        linecolor="grey",
        color="black",
        gridcolor="lightgrey",
        gridwidth=0.5,
        title_font_size=18,
        tickfont_size=12,
        range=[0, None],
        autorange="max",
        rangemode="tozero",
        automargin=True,
        spikethickness=1,
        spikemode="toaxis+across",
    )
    fig.update_layout(
        plot_bgcolor="white",
        title={"text": "LOC trend by Language", "x": 0.5, "xanchor": "center"},
        xaxis={"dtick": "M1"},
        legend_title_font_size=14,
        legend_font_size=14,
    )

    for traces in fig_lang_traces:
        fig.append_trace(traces, row=1, col=1)
    for traces in fig_sum_traces:
        fig.append_trace(traces, row=1, col=1)
    fig.show()
    return fig


def analyze_git_repo_loc(
    repo_path: Path,
    branch: str,
    start_date_str: str,
    end_date_str: str,
    interval: str = "daily",
    lang: list[str] = None,
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

    # Output analysis conditions.
    print(f"- repository:\t{repo_path.resolve()}")
    print(f"- branch:\t{branch}")
    print(f"- since:\t{start_date:%Y-%m-%d %H:%M:%S}")
    print(f"- until:\t{end_date:%Y-%m-%d %H:%M:%S}")
    print(f"- interval:\t{interval}")
    print(f"- language:\t{lang if lang else 'All'}")

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
    print_h1("# Analyse LOC for each commit.")
    for commit in tqdm(commits, desc="Commits"):
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


def find_cloc_path() -> Path:
    """
    Searches for the 'cloc.exe' executable in the system PATH and current working directory.

    The function searches each directory in the PATH environment variable
    for a file named 'cloc.exe'. If it is not found, the function then checks
    the current working directory. If 'cloc.exe' is found and is an executable file,
    its full path is returned.

    Returns:
        Path: The full path to the 'cloc.exe'.

    Raises:
        FileNotFoundError: If 'cloc.exe' is not found.

    Usage example:
        >>> cloc_path = find_cloc_path()
        >>> print(cloc_path)
        WindowsPath('C:/path/to/cloc.exe')
        # this output can vary depending on the actual found path
    """
    cloc_exe_filename: str = "cloc.exe"

    # Find full path of 'cloc.exe' from 'PATH' environment varliable.
    for path in os.environ["PATH"].split(os.pathsep):
        full_path = Path(path) / cloc_exe_filename
        if full_path.is_file() and os.access(str(full_path), os.X_OK):
            print(f"Path: {full_path}")
            return full_path

    # Find 'cloc.exe' from current directory.
    current_dir = Path.cwd()
    full_path = current_dir / cloc_exe_filename
    if full_path.is_file() and os.access(str(full_path), os.X_OK):
        print(f"Path: {full_path}")
        return full_path

    raise FileNotFoundError("Not found cloc.exe.")


def verify_cloc_executable(executable_path: Path) -> None:
    """
    Verifies that the 'cloc' executable is present at the specified path and can be run.

    This function attempts to run `cloc --version` using the given cloc executable path.
    If successful, it prints out the version of cloc. If the executable is not found,
    an error message is printed and the program exits with status code 1.

    Args:
        executable_path (Path): The file system path to the cloc executable.

    Returns:
        None

    Raises:
        FileNotFoundError: If the cloc executable is not found at the given path.

    Usage example:
        >>> from pathlib import Path
        >>> cloc_path = Path('/usr/bin/cloc')
        >>> verify_cloc_executable(cloc_path)
    """
    try:
        version_result = subprocess.run(
            [
                str(executable_path.resolve()),
                "--version",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"- cloc.exe: Ver. {version_result.stdout}")
    except FileNotFoundError as e:
        print(
            f"Error: Not found cloc.exe. {str(e)}",
            file=sys.stderr,
        )
        sys.exit(1)


def make_output_dir(output_dir: Path):
    """
    make_output_dir Make output directory

    Args:
        output_dir (Path): Output directory path
    """
    output_dir.resolve()
    if not output_dir.exists():
        print(f"Make dir. ({output_dir})")
        output_dir.mkdir(parents=True)
    else:
        print(f"Output dir exists. ({output_dir.resolve()})")


def save_dataframe(data: pd.DataFrame, csv_file: Path) -> None:
    """
    save_dataframe Save dataframe type to csv file

    Args:
        data (pd.DataFrame): Data of dataframe type to be saved.
        csv_file (Path): Full path to save csv file
    """
    print(f"- Save: {csv_file}")
    data.to_csv(csv_file)


def print_ok(up: int = 0, back: int = 0):
    """
    print_ok Print OK with GREEN

    Args:
        up (int): Specified number of lines OK is output on the line above
        back (int): Specified number of characters Output OK at the back
    """
    if up > 0:
        print(Cursor.UP(up), end="")
    if back > 0:
        print(Cursor.FORWARD(back), end="")

    print(Style.DIM + "..." + Style.NORMAL + Fore.GREEN + "OK", end="")

    if up > 0:
        print(Cursor.DOWN(up))


def print_h1(text: str):
    """
    print_h1 Print specified text as H1 (header level 1)

    Args:
        text (str): The text to be printed
    """
    print(Fore.CYAN + Style.BRIGHT + text)


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
        type=lambda s: [item.strip() for item in s.split(",")],
        default=None,
        help="Count only the given space separated, case-insensitive languages L1,L2,L3, etc. \n \
        Use 'cloc --show-lang' to see the list of recognized languages.",
    )
    args = parser.parse_args()

    # Colorama initialize.
    colorama.init(autoreset=True)

    # Output program name and description.
    print_h1(f"# Start {parser.prog}.")
    print(Style.DIM + f"- {parser.description}", end=os.linesep + os.linesep)

    # Make output directory.
    print_h1("# Make output directory.")
    output_path: Path = args.output
    make_output_dir(output_path)
    print_ok(up=2, back=50)

    # Find 'cloc.exe' path.
    print_h1("# Find 'cloc.exe' path.")
    cloc_path = find_cloc_path()
    verify_cloc_executable(cloc_path)
    print_ok(up=4, back=50)

    # Analyze LOC against the git repository.
    print_h1("# Analyze LOC against the git repository.")
    loc_data: pd.DataFrame = analyze_git_repo_loc(
        repo_path=args.repo_path,
        branch=args.branch,
        start_date_str=args.start_date,
        end_date_str=args.end_date,
        interval=args.interval,
        lang=args.lang,
    )
    print_ok(up=11, back=50)

    # Forming dataframe type data.
    print_h1("# Forming dataframe type data.")
    loc_trend_by_language: pd.DataFrame = loc_data.pivot_table(
        index="Date", columns="Language", values="code", fill_value=0
    )
    loc_trend_by_language = loc_trend_by_language.astype(int)
    loc_trend_by_language = loc_trend_by_language.sort_values(
        by=loc_trend_by_language.index[-1], axis=1, ascending=False
    )

    trend_of_total_loc: pd.DataFrame = loc_trend_by_language.copy(deep=True)
    trend_of_total_loc["SUM"] = trend_of_total_loc.sum(axis=1)
    trend_of_total_loc = trend_of_total_loc[["SUM"]]
    print_ok(up=1, back=50)

    # Save to csv files.
    print_h1("# Save to csv files.")
    save_dataframe(loc_data, output_path / "loc_data.csv")
    save_dataframe(loc_trend_by_language, output_path / "loc_trend_by_language.csv")
    save_dataframe(trend_of_total_loc, output_path / "trend_of_total_loc.csv")
    print_ok(up=4, back=50)

    # Create charts.
    print_h1("# Create charts.")
    plot: go.Figure = plot_data(
        trend_data=loc_trend_by_language, sum_data=trend_of_total_loc
    )
    plot.write_html(output_path / "report.html")
    print_ok(up=1, back=50)

    print_h1("# LOC Analyze")
    print(
        Cursor.UP()
        + Cursor.FORWARD(50)
        + Style.DIM
        + "..."
        + Style.NORMAL
        + Fore.GREEN
        + "FINISH"
    )
