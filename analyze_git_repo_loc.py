"""
Analyze Git repositories and visualize code LOC.

Author:    Nob Shinjo
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypeVar

import colorama
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from colorama import Cursor, Fore, Style
from git import Commit, InvalidGitRepositoryError, NoSuchPathError, Repo
from plotly.subplots import make_subplots
from tqdm import tqdm


class GitRepoLOCAnalyzer:
    """
    A class analyzing LOC for git repository.
    """

    def __init__(self, repo_path: Path, cache_dir: Path, output_dir: Path):
        """
        Initialize the Git repository Lines of Code (LOC) Analyzer.

        Args:
            repo_path (Path): The path to the git repository.
            cache_dir (Path): The directory where intermediate results can be cached.
            output_dir (Path): The directory where final outputs will be saved.
        """
        # Initialize Git Repo object.
        self._repo_path = repo_path
        """ Git repository path """
        self._repo = self.init_repository()
        """ Git repository object """

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
        start_date: datetime,
        end_date: datetime,
        interval="daily",
        author: str = None,
    ) -> list[Commit]:
        """
        get_commits Get a list of Commit object.

        This function retrieves a list of commits for a specified repository and branch.
        It filters for a specified date range and interval.

        Args:
            branch (str): The name of the branch to retrieve commits from.
            start_date (datetime): The start date for filtering commits.
            end_date (datetime): The end date for filtering commits.
            interval (str, optional): The interval to use for filtering commits.
                                      Defaults to 'daily'. ("hourly", "daily", "weekly", etc.).
            author (str, optional): The author name to filter commits. Defaults to 'None'.

        Raises:
            ValueError: If the provided `interval` is not one of 'daily', 'weekly', or 'monthly'.

        Returns:
            list[Commit]: A list of commit object.
        """

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
        since = f'--since="{start_date.strftime("%Y-%m-%d")}"'
        until = f'--until="{end_date.strftime("%Y-%m-%d")}"'

        # Search and filter commits in order and add them to the list
        # NOTE: Commit dates are ordered by newest to oldest, so filter by end date
        last_added_commit_date = end_date
        commits: list[Commit] = []
        for commit in self._repo.iter_commits(branch, since=since, until=until):
            commit_date = datetime.fromtimestamp(commit.committed_date)
            if commit_date <= last_added_commit_date - delta:
                # commits.append((commit.hexsha, commit_date.strftime("%Y-%m-%d %H:%M:%S")))
                author_name = commit.author.name
                if author is None or author_name == author:
                    commits.append((commit, author_name))
                    last_added_commit_date = commit_date

        print(f"-> {len(commits)} commits found.", end=os.linesep + os.linesep)
        return commits

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
        start_date_str: str,
        end_date_str: str,
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
            start_date_str (str): The start date for filtering commits in 'YYYY-MM-DD' format.
            end_date_str (str): The end date for filtering commits in 'YYYY-MM-DD' format.
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
        analysis_config: list[str] = []
        analysis_config.append(f"- repository:\t{self._repo_path.resolve()}")
        analysis_config.append(f"- branch:\t{branch}")
        analysis_config.append(f"- since:\t{start_date:%Y-%m-%d %H:%M:%S}")
        analysis_config.append(f"- until:\t{end_date:%Y-%m-%d %H:%M:%S}")
        analysis_config.append(f"- interval:\t{interval}")
        analysis_config.append(f"- language:\t{lang if lang else 'All'}")
        analysis_config.append(f"- author:\t{author if author else 'All'}")
        print(f"{os.linesep}".join(analysis_config))

        # Get a list of Commits filtered by the specified date and interval.
        try:
            commits = self.get_commits(
                branch=branch,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                author=author,
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
            json_str (str): A JSON string representation of the data to be converted into a DataFrame.

        Returns:
        df : pandas.DataFrame
            The resulting pandas DataFrame with the 'header' and 'SUM' entries removed,
            and the 'index' column renamed to 'Language'.
        """

        # Decode json string to dict type
        json_dict: dict = json.loads(json_str)
        json_dict.pop("header", None)
        json_dict.pop("SUM", None)

        # Create a dataframe from the json dict type.
        df = pd.DataFrame.from_dict(json_dict, orient="index")
        df.reset_index(inplace=True)
        df.rename(columns={"index": "Language"}, inplace=True)

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
        csv_path = self._output_path / csv_file
        print(f"- Save: {csv_path}")
        data.to_csv(csv_path)

    def create_charts(
        self,
        language_trend_data: pd.DataFrame,
        author_trend_data: pd.DataFrame,
        sum_data: pd.DataFrame,
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
        """
        language_trend_chart = self._chart_builder.build(
            trend_data=language_trend_data, sum_data=sum_data, color_data="Language"
        )
        author_trend_chart = self._chart_builder.build(
            trend_data=author_trend_data, sum_data=sum_data, color_data="Author"
        )

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
            tickformat="%b-%Y",
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
        self._chart.update_layout(
            font_family="Open Sans",
            plot_bgcolor="white",
            title={
                "text": "LOC trend by Language and Author",
                "x": 0.5,
                "xanchor": "center",
                "font_size": 20,
            },
            xaxis={"dtick": "M1"},
            legend_title_font_size=14,
            legend_font_size=14,
        )

        self._chart.show()

    def save_charts(self) -> None:
        """
        Saves the generated charts to HTML format.

        The file is saved to the path specified by _output_path with the filename 'report.html'.
        It's expected that the _chart attribute is already populated with a chart object.
        """
        if self._chart is not None:
            self._chart.write_html(self._output_path / "report.html")


class ChartBuilder:
    """
    A class responsible for building and displaying LOC trend by language and total LOC charts.
    """

    ChartBuilderSelf = TypeVar("ChartBuilderSelf", bound="ChartBuilder")

    def __init__(self) -> None:
        """
        Initializes a new instance of the ChartBuilder class without any data.

        Initialization sets up three primary instance attributes intended to be populated
        with data later on. The _trend_data and _sum_data are placeholders for DataFrame
        objects containing chart data, while _fig is intended to hold a Plotly figure object.
        """
        self._trend_data: pd.DataFrame
        """ A DataFrame containing the trend data of LOC by language. """
        self._sum_data: pd.DataFrame
        """ A DataFrame containing the summarized trend data of total LOC. """
        self._fig: go.Figure = None
        """ The final Plotly figure object that contains the combined area and line plot. """

    def set_trend_data(self, trend_data: pd.DataFrame) -> ChartBuilderSelf:
        """
        Sets the trend data for the chart builder.

        The method assigns the provided pandas DataFrame to the `_trend_data` attribute,
        which presumably is used to build or update a chart figure.

        Args:
            trend_data (pd.DataFrame): The data frame containing trend information
                                       to be visualized.

        Returns:
            ChartBuilderSelf: The instance itself, enabling method chaining.

        This method enables the caller to input new data into the chart builder instance,
        allowing for dynamic updates and modifications of the visualization.
        """
        self._trend_data = trend_data
        return self

    def set_sum_data(self, sum_data: pd.DataFrame) -> ChartBuilderSelf:
        """
        Sets the summary data for the chart builder.

        This method assigns the provided pandas DataFrame to the `_sum_data` attribute,
        which is likely used for representing aggregate or summary statistics in a chart.

        Args:
            sum_data (pd.DataFrame): A data frame containing summary statistics or aggregated
                                     data to be used in the chart.

        Returns:
            ChartBuilderSelf: The instance of the chart builder. This allows for chaining
                              method calls to configure the chart builder further.

        Example usage might involve setting up a series of configurations to a chart builder:
        ```
        chart_builder = (
            ChartBuilder()
            .set_trend_data(trend_frame)
            .set_sum_data(summary_frame)
            ...
        )
        ```

        By enabling this fluid interface pattern, the chart builder can progressively be
        configured with different data components for a final visualization.
        """
        self._sum_data = sum_data
        return self

    def create_fig(self) -> ChartBuilderSelf:
        """
        Initializes a figure object with a single subplot for the chart.

        The method sets the `_fig` attribute of the instance to a new figure
        with predefined x and y axis titles set to "Date" and "LOC" respectively.

        Returns:
            ChartBuilderSelf: The instance itself, allowing for method chaining.

        This is typically used to prepare the plotting object before adding traces,
        layouts or other specific settings required for the final visualization. After calling
        this method, additional configurations can be applied on the `_fig` attribute.
        """
        self._fig: go.Figure = make_subplots(
            rows=1,
            cols=1,
            specs=[[{"secondary_y": True}]],
        )
        return self

    def create_trend_trace(self, color_data: str) -> ChartBuilderSelf:
        """
        Generates a trend trace from the trend data and appends it to the chart figure.

        This method creates an area plot representing the trends of lines of code (LOC)
        by language over time using the `_trend_data` attribute. It then extracts the
        traces from that plot and appends each trace to the first row and column of the
        main figure maintained by this instance (`_fig`).

        The plot is presumably created using Plotly Express, which is indicated by the `px`
        prefix on the `area()` function.

        Args:
            color_data (str): The name of the column in the trend data frame that contains
                              the color data for the area plot.

        Returns:
            ChartBuilderSelf: The instance of the chart builder with the new trend trace
                                appended to its figure. This supports chaining further
                                configuration calls to the chart builder.

        Example usage might involve creating a trend trace as part of configuring a chart builder:
        ```
        chart_builder = (
            ChartBuilder()
            .set_trend_data(trend_frame)
            .create_trend_trace()
            ...
        )
        ```

        This docstring assumes that `_trend_data` and `_fig` are pre-existing attributes of the
        instance that have been appropriately set. `_trend_data` should be a DataFrame containing
        the necessary data for plotting, while `_fig` should be a Plotly figure object that can
        have traces appended to it.
        """
        # Field area plot of LOC trend
        fig_lang = px.area(
            data_frame=self._trend_data, color=color_data, line_shape=None
        )
        fig_lang_traces = []
        for trace in range(len(fig_lang["data"])):
            fig_lang_traces.append(fig_lang["data"][trace])

        for traces in fig_lang_traces:
            self._fig.append_trace(traces, row=1, col=1)

        return self

    def create_sum_trace(self) -> ChartBuilderSelf:
        """
        Creates and appends a summary line trace to the chart figure.

        This method uses the `_sum_data` attribute to generate a line plot with markers
        representing the total lines of code (LOC) trend. Each trace generated from
        `fig_sum` is then configured to not show a legend entry by setting the
        'showlegend' property to False. The traces are collected in a list and
        subsequently appended to the main figure's first row and column.

        Returns:
            ChartBuilderSelf: The instance itself is returned, enabling method chaining
                              with other configuration functions of the chart builder.

        Example usage might be:
        ```
        chart_builder = (
            ChartBuilder()
            .set_sum_data(summary_data_frame)
            .create_sum_trace()
            ...
        )
        ```

        This docstring assumes there is an internal representation for the chart in the form
        of `_sum_data`, which should be a pandas DataFrame containing the data needed for the
        plot, and `_fig`, which should be a Plotly figure object available for appending
        traces to it.
        """
        # Line plots of total LOC trend
        fig_sum = px.line(data_frame=self._sum_data, y="SUM", markers=True)
        for trace in fig_sum["data"]:
            trace["showlegend"] = False
            trace["name"] = "SUM"
            trace["marker"] = {"size": 8, "color": "#636EFA"}
            trace["line"] = {"width": 2, "color": "#636EFA"}
            self._fig.add_trace(trace, row=1, col=1, secondary_y=False)

        return self

    def create_diff_trace(self) -> ChartBuilderSelf:
        """
        Adds a differential trace to an existing plotly figure within the ChartBuilder instance.

        This method creates a line chart using the internal summed data
        focusing on the 'Diff' column.
        It then adds this newly created trace to the main figure without including it in the legend.
        The trace is placed on a secondary y-axis in the first row and column of the subplot grid.

        Returns:
            self (ChartBuilder): Returns the instance itself for method chaining purposes.
        """
        fig_diff = px.line(data_frame=self._sum_data, y="Diff", markers=True)
        for trace in fig_diff["data"]:
            trace["showlegend"] = False
            trace["name"] = "Diff"
            trace["marker"] = {"size": 8, "color": "#EF553B"}
            trace["line"] = {"width": 2, "color": "#EF553B"}
            self._fig.add_trace(trace, row=1, col=1, secondary_y=True)
        return self

    def update_fig(self) -> ChartBuilderSelf:
        """
        Updates the axes and layout of the `_fig` attribute with a specific style.

        This method configures various properties for both x and y axes, such as
        visibility of grid lines, color and width of lines, angle and format of ticks,
        as well as updating the layout of the figure to adjust background color, title,
        and legend styling.

        Returns:
            ChartBuilderSelf: The instance itself, enabling method chaining.

        After the call to this method, the `_fig` attribute will be styled according to
        the specifications set within this method and can be further manipulated or displayed.
        """
        self._fig.update_xaxes(
            showline=True,
            linewidth=1,
            linecolor="grey",
            color="black",
            gridcolor="lightgrey",
            gridwidth=0.5,
            title_text="Date",
            title_font_size=18,
            side="bottom",
            tickfont_size=14,
            tickangle=-45,
            tickformat="%b-%Y",
            automargin=True,
        )
        self._fig.update_yaxes(
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
        self._fig.update_yaxes(
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
        self._fig.update_layout(
            font_family="Open Sans",
            plot_bgcolor="white",
            title={
                "text": "LOC trend by Language",
                "x": 0.5,
                "xanchor": "center",
                "font_size": 20,
            },
            xaxis={"dtick": "M1"},
            legend_title_font_size=14,
            legend_font_size=14,
        )
        return self

    def build(
        self, trend_data: pd.DataFrame, sum_data: pd.DataFrame, color_data: str
    ) -> go.Figure:
        """
        Constructs the chart by setting data and creating figure and traces.

        This method configures the chart builder with the given `trend_data` and
        `sum_data`, creates a new figure, then creates and attaches the necessary
        trend and summary line traces, and finally updates the figure layout before
        returning it.

        Parameters:
            trend_data (pd.DataFrame): A pandas DataFrame containing the data to be used for
                                       trend trace creation.
            sum_data (pd.DataFrame): A pandas DataFrame containing the data to be used for
                                     summary trace creation.

        Returns:
            ChartBuilderSelf: The Plotly figure object configured with the trend and summary
                              traces, ready for display or further modification.
        """
        self.set_trend_data(trend_data)
        self.set_sum_data(sum_data)
        self.create_fig()
        self.create_trend_trace(color_data)
        self.create_sum_trace()
        self.create_diff_trace()
        self.update_fig()
        return self._fig

    def show(self) -> None:
        """
        Displays the constructed chart in a browser window.

        This method should be called after the chart has been built using the
        `build` method. It uses the internal figure instance (`_fig`) to render
        the chart using Plotly's default rendering engine.
        """
        self._fig.show()


class ColoredConsolePrinter:
    """
    A class designed to provide colored console printing functionalities.
    This class uses the Colorama library to enable cross-platform support for colored
    terminal output. It can be used to print text in various colors to the console,
    improving the readability and visual appeal of command-line programs.
    """

    def __init__(self) -> None:
        """
        Initializes a new instance of the ColoredConsolePrinter class.
        Sets up the Colorama library to autoreset after each print statement, ensuring that
        the default console color is restored after each colored output.
        """
        # Colorama initialize.
        colorama.init(autoreset=True)

    def move_cursor(self, up: int = 0, down: int = 0, forward: int = 0) -> None:
        """
        Moves the cursor position in the terminal window.

        This method uses ANSI escape codes to move the cursor position without
        altering the text that is already on the screen. It can move the cursor up
        a specified number of lines and forward a specified number of characters.

        Args:
            up (int): The number of lines to move the cursor up.
            down (int): The number of lines to move the cursor down.
            forward (int): The number of characters to move the cursor forward.
        """
        if up > 0:
            print(Cursor.UP(up), end="")
        if down > 0:
            print(Cursor.DOWN(down), end="")
        if forward > 0:
            print(Cursor.FORWARD(forward), end="")

    def print_colored(
        self, text: str, color: str, bright: bool = False, end=os.linesep
    ) -> None:
        """
        Prints the specified text with the desired color and brightness.

        This method allows for printing colored text to the terminal by leveraging
        ANSI escape codes provided by the Colorama library. Additionally, it can
        move the cursor before and after printing, based on the keyword arguments
        passed for cursor movement.

        Args:
            text (str): The text to be printed.
            color (str): The color code for the text. Expected to be a Colorama Fore attribute.
            bright (bool, optional): If True, the text will be printed in a brighter shade.

        Examples:
            - print_colored("Hello, World!", Fore.RED)
            - print_colored("Attention!", Fore.YELLOW, bright=True, up=1, forward=10)
        """
        style = Style.BRIGHT if bright else ""
        print(style + color + text, end=end)

    def print_ok(self, up: int = 0, forward: int = 0) -> None:
        """
        print_ok Print OK with GREEN
        Args:
            up (int): Specified number of lines OK is output on the line above
            forward (int): Specified number of characters Output OK at the forward
        """
        self.move_cursor(up=up, forward=forward)
        self.print_colored("OK", color=Fore.GREEN)
        self.move_cursor(down=up)

    def print_h1(self, text: str) -> None:
        """
        print_h1 Print specified text as H1 (header level 1)
        Args:
            text (str): The text to be printed
        """
        self.print_colored(text, color=Fore.CYAN, bright=True)


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
    parser.add_argument(
        "--author-name",
        type=str,
        default=None,
        help="Author name to filter commits",
    )
    parser.add_argument(
        "--clear_cache",
        action="store_true",
        help="If set, the cache will be cleared before executing the main function.",
    )

    args = parser.parse_args()

    # Get to Current directory
    current_path: Path = Path.cwd()
    # Initialize ColoredConsolePrinter
    console = ColoredConsolePrinter()

    # Output program name and description.
    console.print_h1(f"# Start {parser.prog}.")
    print(Style.DIM + f"- {parser.description}", end=os.linesep + os.linesep)

    # Create GitRepoLOCAnalyzer
    try:
        console.print_h1("# Initialize LOC analyzer.")
        analyzer = GitRepoLOCAnalyzer(
            repo_path=args.repo_path,
            cache_dir=args.output / ".cache",
            output_dir=args.output,
        )
        console.print_ok(up=7, forward=50)
    except FileNotFoundError as ex:
        print(f"Error: {str(ex)}", file=sys.stderr)
        sys.exit(1)
    # Remove cache files
    try:
        if args.clear_cache:
            console.print_h1("# Remove cache files.")
            analyzer.clear_cache_files()
            console.print_ok(up=2, forward=50)
    except FileNotFoundError as ex:
        print(f"Error: {str(ex)}", file=sys.stderr)
        sys.exit(1)

    # Analyze LOC against the git repository.
    console.print_h1("# Analyze LOC against the git repository.")
    loc_data = analyzer.analyze_git_repo_loc(
        branch=args.branch,
        start_date_str=args.start_date,
        end_date_str=args.end_date,
        interval=args.interval,
        lang=args.lang,
        author=args.author_name,
    )
    console.print_ok(up=12, forward=50)

    # Forming dataframe type data.
    console.print_h1("# Forming dataframe type data.")

    # Pivot table by language
    loc_trend_by_language: pd.DataFrame = loc_data.pivot_table(
        index="Date", columns="Language", values="code", fill_value=0
    )
    loc_trend_by_language = loc_trend_by_language.astype(int)
    if not loc_trend_by_language.empty:
        loc_trend_by_language = loc_trend_by_language.sort_values(
            by=loc_trend_by_language.index[-1], axis=1, ascending=False
        )
    else:
        raise ValueError(
            f"{loc_trend_by_language} is empty. Please check the filtering conditions."
        )

    # Pivot table by author
    loc_trend_by_author: pd.DataFrame = loc_data.pivot_table(
        index="Date", columns="Author", values="code", fill_value=0
    )
    loc_trend_by_author = loc_trend_by_author.astype(int)
    if not loc_trend_by_author.empty:
        loc_trend_by_author = loc_trend_by_author.sort_values(
            by=loc_trend_by_author.index[-1], axis=1, ascending=False
        )
    else:
        raise ValueError(
            f"{loc_trend_by_author} is empty. Please check the filtering conditions."
        )

    # Total LOC trend
    trend_of_total_loc: pd.DataFrame = loc_trend_by_language.copy(deep=True)
    trend_of_total_loc["SUM"] = trend_of_total_loc.sum(axis=1)
    trend_of_total_loc = trend_of_total_loc[["SUM"]]
    trend_of_total_loc["Diff"] = trend_of_total_loc["SUM"].diff()
    delta_data = trend_of_total_loc.reset_index()
    console.print_ok(up=1, forward=50)

    # Save to csv files.
    console.print_h1("# Save to csv files.")
    analyzer.save_dataframe(loc_data, "loc_data.csv")
    analyzer.save_dataframe(loc_trend_by_language, "loc_trend_by_language.csv")
    analyzer.save_dataframe(loc_trend_by_author, "loc_trend_by_author.csv")
    analyzer.save_dataframe(trend_of_total_loc, "trend_of_total_loc.csv")
    console.print_ok(up=5, forward=50)

    # Create charts.
    console.print_h1("# Create charts.")
    analyzer.create_charts(
        language_trend_data=loc_trend_by_language,
        author_trend_data=loc_trend_by_author,
        sum_data=trend_of_total_loc,
    )
    analyzer.save_charts()
    console.print_ok(up=1, forward=50)

    console.print_h1("# LOC Analyze")
    print(Cursor.UP() + Cursor.FORWARD(50) + Fore.GREEN + "FINISH")
