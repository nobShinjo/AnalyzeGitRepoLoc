"""
This module provides the GitRepoLOCAnalyzer class, which is used to analyze lines of code (LOC) in a Git repository.
The class offers functionalities to initialize a Git repository, create output directories, find and verify the 'cloc' executable,
retrieve commits, run 'cloc' for LOC analysis, and generate charts for visualizing LOC trends.
Classes:
    GitRepoLOCAnalyzer: A class for analyzing LOC in a Git repository.
Functions:
    __init__(self, repo_path: Path, cache_dir: Path, output_dir: Path):
    init_repository(self) -> Repo:
    make_output_dir(self, output_dir: Path) -> Path:
    clear_cache_files(self):
    find_cloc_path(self) -> Path:
    verify_cloc_executable(self, executable_path: Path) -> None:
    get_commits(self, branch: str, start_date: datetime, end_date: datetime, interval="daily", author: str = None) -> list[tuple[Commit, str]]:
        Get a list of Commit objects.
    branch_exists(self, branch: str) -> bool:
    run_cloc(self, commit: Commit, lang: list[str] = None) -> str:
    analyze_git_repo_loc(self, branch: str, start_date_str: str, end_date_str: str, interval: str = "daily", lang: list[str] = None, author: str = None) -> pd.DataFrame:
        Analyze and extract LOC statistics from a Git repository.
    convert_json_to_dataframe(self, json_str):
    save_dataframe(self, data: pd.DataFrame, csv_file: Path) -> None:
        Save dataframe type to csv file.
    create_charts(self, language_trend_data: pd.DataFrame, author_trend_data: pd.DataFrame, sum_data: pd.DataFrame, output_path: Path, interval: str):
    save_charts(self, output_path: Path) -> None:
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from git import Commit, InvalidGitRepositoryError, NoSuchPathError, Repo, exc
from plotly.subplots import make_subplots
from tqdm import tqdm

from .chart_builder import ChartBuilder


class GitRepoLOCAnalyzer:
    """
    A class analyzing LOC for git repository.
    """

    def __init__(
        self, repo_path: Path, branch_name: str, cache_dir: Path, output_dir: Path
    ):
        """
        Initialize the Git repository Lines of Code (LOC) Analyzer.

        Args:
            repo_path (Path): The path to the git repository.
            branch_name (str): The name of the branch to analyze.
            cache_dir (Path): The directory where intermediate results can be cached.
            output_dir (Path): The directory where final outputs will be saved.
        """
        # Initialize Git Repo object.
        self._repo_path = repo_path
        """ Git repository path """
        self._repo = self.init_repository()
        """ Git repository object """
        self._branch_name = branch_name
        """ Active branch name """
        # Make output directory.
        self._cache_path = self.make_output_dir(cache_dir / repo_path.name).resolve()
        """ Path to cache directory """
        self._output_path = self.make_output_dir(output_dir / repo_path.name).resolve()
        """ Path to output directory """

        # Find 'cloc.exe' path.
        self._cloc_path = self.find_cloc_path()
        """ Path to 'cloc.exe' """
        self.verify_cloc_executable(self._cloc_path)

        # Initialize ChartBuilder
        self._chart_builder: ChartBuilder = ChartBuilder()
        self._chart: go.Figure = None
        """ The final Plotly figure object that contains the combined area and line plot. """

    def init_repository(self) -> Repo:
        """
        Initializes and returns a Repo object if the repository is valid.

        This method attempts to create a Repo object using the directory path
        provided in `self.repo_path`. If the path does not represent a valid Git
        repository or the path does not exist, it will print an error message to
        stderr and re-raise the exception.

        Returns:
            Repo: A Repo object representing the Git repository at `self.repo_path`.

        Raises:
            InvalidGitRepositoryError: An error is raised if `self.repo_path` is
                                       not a valid Git repository.
            NoSuchPathError: An error is raised if `self.repo_path` does not exist.
        """
        try:
            return Repo(self._repo_path)
        except InvalidGitRepositoryError as e:
            print(
                f"InvalidGitRepositoryError: Not a git repository. {str(e)}",
                file=sys.stderr,
            )
            raise
        except NoSuchPathError as e:
            print(f"NoSuchPathError: No such path. {str(e)}", file=sys.stderr)
            raise

    def make_output_dir(self, output_dir: Path) -> Path:
        """
        Attempts to create the directory specified by `output_dir`, if it does not already exist.

        Args:
            output_dir (Path): The path of the output directory to be created.

        Returns:
            Path: The resolved path of the output directory which may have been created.

        This method will resolve the provided `output_dir` and check its existence.
        If the directory does not exist, it will create the directory and all its
        required parents, then print a confirmation message. If the directory already exists,
        it will simply print an informational message stating that the directory exists.
        In both cases, the resolved output directory path is returned.
        """
        output_dir.resolve()
        if not output_dir.exists():
            print(f"Make directory. ({output_dir})")
            output_dir.mkdir(parents=True)
        else:
            print(f"Directory exists. ({output_dir.resolve()})")
        return output_dir

    def clear_cache_files(self):
        """
        Delete all files located in the directory specified by the `_cache_path` attribute.

        This method checks if `_cache_path` exists and is a directory. If so,
        it proceeds to iterate through all files within this directory (including
        subdirectories) and deletes each file.

        Raises:
            AttributeError: If `_cache_path` does not exist or is not a directory.
        """
        if self._cache_path.exists() and self._cache_path.is_dir():
            for file in tqdm(self._cache_path.glob("**/*")):
                if file.is_file():
                    file.unlink()

    def find_cloc_path(self) -> Path:
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
        cloc_exe_filename: str = "cloc.exe" if os.name == "nt" else "cloc"

        # Find full path of 'cloc.exe' from 'PATH' environment variable.
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

    def verify_cloc_executable(self, executable_path: Path) -> None:
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
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Error executing cloc: {e.stderr}") from e

    def get_commits(
        self,
        branch: str,
        since: datetime,
        until: datetime,
        interval="daily",
        author: str = None,
    ) -> list[tuple[Commit, str]]:
        """
        get_commits Get a list of Commit object.

        This function retrieves a list of commits for a specified repository and branch.
        It filters for a specified date range and interval.

        Args:
            branch (str): The name of the branch to retrieve commits from.
            since (datetime): The start date for filtering commits.
            until (datetime): The end date for filtering commits.
            interval (str, optional): The interval to use for filtering commits.
                                      Defaults to 'daily'. ("hourly", "daily", "weekly", etc.).
            author (str, optional): The author name to filter commits. Defaults to 'None'.

        Raises:
            ValueError: If the provided `interval` is not one of 'daily', 'weekly', or 'monthly'.

        Returns:
            list[tuple[Commit, str]]: A list of tuples containing the Commit object and author name.
        """

        # Check if the branch exists
        if not self.branch_exists(branch):
            raise RuntimeError(f"Branch '{branch}' does not exist.")

        # Set the timedelta object that defines the interval.
        # NOTE: Approximate average length of month in days
        intervals = {
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "monthly": timedelta(days=30),
        }
        delta = intervals.get(interval)
        if not delta:
            raise ValueError(
                "Invalid interval. Choose 'daily', 'weekly', or 'monthly'."
            )

        # Start and end dates to filter
        since_str = f'--since="{since.strftime("%Y-%m-%d")}"'
        until_str = f'--until="{until.strftime("%Y-%m-%d")}"'

        # Search and filter commits in order and add them to the list
        # NOTE: Commit dates are ordered by newest to oldest, so filter by end date
        last_added_commit_date = until
        commits: list[tuple[Commit, str]] = []
        for commit in self._repo.iter_commits(branch, since=since_str, until=until_str):
            commit_date = datetime.fromtimestamp(commit.committed_date)
            if commit_date <= last_added_commit_date - delta:
                # commits.append((commit.hexsha, commit_date.strftime("%Y-%m-%d %H:%M:%S")))
                author_name = commit.author.name
                if author is None or author_name == author:
                    commits.append((commit, author_name))
                    last_added_commit_date = commit_date

        print(f"-> {len(commits)} commits found.", end=os.linesep + os.linesep)
        return commits

    def branch_exists(self, branch: str) -> bool:
        """
        Check if a branch exists in the repository.

        Args:
            branch (str): The branch name to check.

        Returns:
            bool: True if the branch exists, False otherwise.
        """
        try:
            self._repo.git.show_ref(f"refs/heads/{branch}")
            return True
        except exc.GitCommandError:
            return False

    def run_cloc(self, commit: Commit, lang: list[str] = None) -> str:
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
                    str(self._cloc_path.resolve()),
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
        except subprocess.CalledProcessError as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError as e:
            print(
                f"Error: Not found cloc.exe. {str(e)}",
                file=sys.stderr,
            )
            sys.exit(1)
        return result.stdout

    def analyze_git_repo_loc(
        self,
        branch: str,
        since_str: str,
        until_str: str,
        interval: str = "daily",
        lang: list[str] = None,
        author: str = None,
    ) -> pd.DataFrame:
        """
        analyze_git_repo_loc Analyze and extract LOC statistics from a Git repository.

        Specified repository path, branch name, date range, and an optional interval, this function
        extracts the counts of lines of code, including the number of files, comments, blank,
        and lines of code per language. It runs `cloc` for each commit within the specified range
        and compiles the results into a single DataFrame.

        Args:
            branch (str): The name of the branch to retrieve commits from.
            since_str (str): The start date for filtering commits in 'YYYY-MM-DD' format.
            until_str (str): The end date for filtering commits in 'YYYY-MM-DD' format.
            interval (str, optional): The interval to use for filtering commits.
                                      Defaults to 'daily'. ("hourly", "daily", "weekly", etc.).
            lang (list[str], optional): List of languages to search. Defaults to 'None'
            author (str, optional): The author name to filter commits. Defaults to 'None'.

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
            if since_str is None:
                since: datetime = datetime.strptime("1970-01-01", "%Y-%m-%d")
            else:
                since: datetime = datetime.strptime(since_str, "%Y-%m-%d")

            if until_str is None:
                until: datetime = datetime.now()
            else:
                until: datetime = datetime.strptime(until_str, "%Y-%m-%d")
        except ValueError as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            sys.exit(1)

        # Output analysis conditions.
        analysis_config: list[str] = []
        analysis_config.append(f"- repository:\t{self._repo_path.resolve()}")
        analysis_config.append(f"- branch:\t{branch}")
        analysis_config.append(f"- since:\t{since:%Y-%m-%d %H:%M:%S}")
        analysis_config.append(f"- until:\t{until:%Y-%m-%d %H:%M:%S}")
        analysis_config.append(f"- interval:\t{interval}")
        analysis_config.append(f"- language:\t{lang if lang else 'All'}")
        analysis_config.append(f"- author:\t{author if author else 'All'}")
        print(f"{os.linesep}".join(analysis_config))

        # Get a list of Commits filtered by the specified date and interval.
        try:
            commits = self.get_commits(
                branch=branch,
                since=since,
                until=until,
                interval=interval,
                author=author,
            )
        except ValueError as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            sys.exit(1)

        if len(commits) == 0:
            print("Error: Not found commits in the specified branch.", file=sys.stderr)
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

        # Change the directory to the repository path.
        origin_path: Path = Path.cwd()
        os.chdir(self._repo_path)

        # Analyse LOC for each commit.
        print("Analyse LOC for each commit.")
        for commit, author_name in tqdm(commits, desc="Commits"):
            # Check for cache files
            cloc_result_file: Path = self._cache_path / f"{commit.hexsha}.json"
            cloc_result: str = None

            if cloc_result_file.exists():
                with cloc_result_file.open(mode="r") as file:
                    cloc_result = file.read()
            else:
                # Run "cloc.exe"
                cloc_result = self.run_cloc(commit=commit, lang=lang)
                with cloc_result_file.open(mode="w") as file:
                    file.write(cloc_result)

            df = self.convert_json_to_dataframe(cloc_result)

            # Insert Commit and Date columns at the head of columns in the dataframe.
            df.insert(0, "Commit", commit.hexsha)
            committed_date = datetime.fromtimestamp(commit.committed_date)
            df.insert(1, "Date", committed_date.strftime("%Y-%m-%d %H:%M:%S"))
            df.insert(2, "Author", author_name)
            # Concatenate data frames
            cloc_df = pd.concat([cloc_df, df])

        cloc_df.reset_index(inplace=True, drop=True)

        # Return to original directory.
        os.chdir(origin_path)

        return cloc_df

    def convert_json_to_dataframe(self, json_str):
        """
        Convert a JSON string to a pandas DataFrame after removing specified keys.

        This function takes a JSON string and decodes it into a dictionary, removes
        the 'header' and 'SUM' elements if they exist, and then converts it into a
        pandas DataFrame. The index of the DataFrame is reset, and the first column
        is renamed to 'Language'.

        Args:
            json_str (str): A JSON string representation of the data to be converted
                            into a DataFrame.

        Returns:
        df : pandas.DataFrame
            The resulting pandas DataFrame with the 'header' and 'SUM' entries removed,
            and the 'index' column renamed to 'Language'.
        """
        try:
            # Decode json string to dict type
            json_dict: dict = json.loads(json_str)
            json_dict.pop("header", None)
            json_dict.pop("SUM", None)

            # Create a dataframe from the json dict type.
            df = pd.DataFrame.from_dict(json_dict, orient="index")
            df.reset_index(inplace=True)
            df.rename(columns={"index": "Language"}, inplace=True)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            return pd.DataFrame()

        return df

    def save_dataframe(self, data: pd.DataFrame, csv_file: Path) -> None:
        """
        save_dataframe Save dataframe type to csv file

        Args:
            data (pd.DataFrame): Data of dataframe type to be saved.
            csv_file (Path): Full path to save csv file

        Returns:
            None
        """
        print(f"- Save: {csv_file}")
        data.to_csv(csv_file)

    def create_charts(
        self,
        language_trend_data: pd.DataFrame,
        author_trend_data: pd.DataFrame,
        sum_data: pd.DataFrame,
        output_path: Path,
        interval: str,
    ):
        """
        Creates charts using the provided trend and summation data.

        This method takes a trend dataframe and a summation dataframe,
        builds a chart using the internal _chart_builder.
        Args:
            language_trend_data (pd.DataFrame):
                A pandas DataFrame containing the trend data of LOC by language.
            author_trend_data (pd.DataFrame):
                A pandas DataFrame containing the trend data of LOC by author.
            sum_data (pd.DataFrame): A pandas DataFrame that contains the summary data.
            output_path (Path): The path to save the chart HTML file.
            interval (str): The interval to use for formatting the x-axis ticks.
                            Should be one of 'daily', 'weekly', or 'monthly'.
        """
        language_trend_chart = self._chart_builder.build(
            trend_data=language_trend_data,
            sum_data=sum_data,
            color_data="Language",
            interval=interval,
            repo_name=self._repo_path.name,
            branch_name=self._repo.active_branch.name,
        )
        language_trend_chart.write_html(output_path / "language_trend_chart.html")

        author_trend_chart = self._chart_builder.build(
            trend_data=author_trend_data,
            sum_data=sum_data,
            color_data="Author",
            interval=interval,
            repo_name=self._repo_path.name,
            branch_name=self._repo.active_branch.name,
        )
        author_trend_chart.write_html(output_path / "author_trend_chart.html")

        # Combine two charts
        self._chart = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            subplot_titles=("Language Trend", "Author Trend"),
            vertical_spacing=0.1,
            specs=[[{"secondary_y": True}], [{"secondary_y": True}]],
        )

        # Add traces from language_trend_chart
        for trace in language_trend_chart["data"]:
            self._chart.add_trace(trace, row=1, col=1)

        # Add traces from author_trend_chart
        for trace in author_trend_chart["data"]:
            self._chart.add_trace(trace, row=2, col=1)

        # Update layout
        self._chart.update_xaxes(
            showline=True,
            linewidth=1,
            linecolor="grey",
            color="black",
            gridcolor="lightgrey",
            gridwidth=0.5,
            title_text="Date",
            title_font_size=18,
            tickfont_size=14,
            tickangle=-45,
            tickformat=language_trend_chart["layout"]["xaxis"]["tickformat"],
            automargin=True,
        )
        self._chart.update_yaxes(
            secondary_y=False,
            showline=True,
            linewidth=1,
            linecolor="grey",
            color="black",
            gridcolor="lightgrey",
            gridwidth=0.5,
            title_text="LOC",
            title_font_size=18,
            tickfont_size=14,
            range=[0, None],
            autorange="max",
            rangemode="tozero",
            automargin=True,
            spikethickness=1,
            spikemode="toaxis+across",
        )
        self._chart.update_yaxes(
            secondary_y=True,
            showline=True,
            linewidth=1,
            linecolor="grey",
            color="black",
            gridcolor="lightgrey",
            gridwidth=0.5,
            title_text="Difference of LOC",
            title_font_size=18,
            tickfont_size=14,
            range=[0, None],
            autorange="max",
            rangemode="tozero",
            automargin=True,
            spikethickness=1,
            spikemode="toaxis+across",
            overlaying="y",
            side="right",
        )
        chat_title = f"LOC trend by Language and Author - {self._repo_path.name} ({self._branch_name})"
        self._chart.update_layout(
            font_family="Open Sans",
            plot_bgcolor="white",
            title={
                "text": chat_title,
                "x": 0.5,
                "xanchor": "center",
                "font_size": 20,
            },
            xaxis={"dtick": "M1"},
            legend_title_font_size=14,
            legend_font_size=14,
        )

        self._chart.show()

    def save_charts(self, output_path: Path) -> None:
        """
        Saves the generated charts to HTML format.

        The file is saved to the path specified by _output_path with the filename 'report.html'.
        It's expected that the _chart attribute is already populated with a chart object.

        Args:
            output_path (Path): The path to save the chart HTML file.
        """
        if self._chart is not None:
            self._chart.write_html(output_path / "report.html")
