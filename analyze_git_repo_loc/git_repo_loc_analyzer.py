"""

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

from analyze_git_repo_loc.chart_builder import ChartBuilder
from analyze_git_repo_loc.language_comment import LanguageComment
from analyze_git_repo_loc.language_extensions import LanguageExtensions


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
        pass

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
        pass

    def verify_cloc_executable(self, executable_path: Path) -> None:
        pass

    def get_commits(
        self,
        branch: str,
        since: datetime,
        until: datetime,
        interval="daily",
        author: str = None,
    ) -> list[tuple[Commit, str]]:
        pass

    def is_branch_exists(self, repo_path: PathLike, branch_name: str) -> bool:
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
        pass
    def analyze_git_repo_loc(
        self,
        branch: str,
        since_str: str,
        until_str: str,
        interval: str = "daily",
        lang: list[str] = None,
        author: str = None,
    ) -> pd.DataFrame:

    def convert_json_to_dataframe(self, json_str):
        pass

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
        sub_title: str,
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
            sub_title (str): The sub-title to include in the chart title.
        """
        language_trend_chart = self._chart_builder.build(
            trend_data=language_trend_data,
            sum_data=sum_data,
            color_data="Language",
            interval=interval,
            repo_name=self._repo_path.name,
            branch_name=self._branch_name,
        )
        language_trend_chart.write_html(output_path / "language_trend_chart.html")

        author_trend_chart = self._chart_builder.build(
            trend_data=author_trend_data,
            sum_data=sum_data,
            color_data="Author",
            interval=interval,
            repo_name=self._repo_path.name,
            branch_name=self._branch_name,
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
        chat_title = f"LOC trend by Language and Author - {sub_title}"
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
