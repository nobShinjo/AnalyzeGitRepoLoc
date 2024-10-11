"""

"""

from datetime import datetime
from pathlib import Path
from typing import Union

import pandas as pd
import plotly.graph_objects as go
from git import GitCommandError, PathLike, Repo
from plotly.subplots import make_subplots
from pydriller import Repository
from tqdm import tqdm

from analyze_git_repo_loc.chart_builder import ChartBuilder
from analyze_git_repo_loc.language_comment import LanguageComment
from analyze_git_repo_loc.language_extensions import LanguageExtensions


class GitRepoLOCAnalyzer:
    """
    A class analyzing LOC for git repository.
    """

    def __init__(
        self,
        repo_path: Union[Path, str],
        branch_name: str,
        cache_dir: Path,
        output_dir: Path,
        since: datetime = None,
        to: datetime = None,
        from_tag: str = None,
        to_tag: str = None,
        authors: list[str] = None,
        languages: list[str] = None,
    ):
        """
        Initialize the Git repository Lines of Code (LOC) Analyzer.

        Args:
            repo_path (Union[Path,str]): The path to the git repository.
            branch_name (str): The name of the branch to analyze.
            cache_dir (Path): The directory where intermediate results can be cached.
            output_dir (Path): The directory where final outputs will be saved.
            since (datetime): The start date for filtering commits.
            to (datetime): The end date for filtering commits.
            from_tag (str): The start tag for filtering commits.
            to_tag (str): The end tag for filtering commits.
            authors (list[str]): A list of author names to filter commits.
            languages (list[str]): A list of languages to filter commits.
        """
        # Initialize Git Repo object.
        self._repo_path = repo_path
        """ Git repository path """
        self._branch_name = branch_name
        """ Branch name to analyze """

        # Make output directory.
        self._cache_path = self.make_output_dir(cache_dir / repo_path.name).resolve()
        """ Path to cache directory """
        self._output_path = self.make_output_dir(output_dir / repo_path.name).resolve()
        """ Path to output directory """

        # pydriller options
        self._since = since
        """ Start date for filtering commits """
        self._to = to
        """ End date for filtering commits """
        self._from_tag = from_tag
        """ Start tag for filtering commits """
        self._to_tag = to_tag
        """ End tag for filtering commits """
        self._authors = authors
        """ List of author names to filter commits """
        self._languages = languages
        """ List of languages to filter commits """

        self._language_extensions = LanguageExtensions.get_extensions(
            language=languages
        )
        """ Language extensions to filter commits """

        # Initialize ChartBuilder
        self._chart_builder: ChartBuilder = ChartBuilder()
        self._chart: go.Figure = None
        """ The final Plotly figure object that contains the combined area and line plot. """

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

    def is_branch_exists(self, repo_path: PathLike, branch_name: str) -> bool:
        """
        Check if a branch exists in the given Git repository.

        Args:
            repo_path (PathLike): The file system path to the Git repository.
            branch_name (str): The name of the branch to check for existence.

        Returns:
            bool: True if the branch exists, False otherwise.

        Raises:
            GitCommandError: If there is an error executing Git commands.
            AttributeError: If there is an attribute error while accessing the repository.

        """
        try:
            repo = Repo(repo_path)
            return branch_name in repo.heads
        except (GitCommandError, AttributeError):
            return False

    def is_comment_or_empty_line(self, line: str, language: str) -> bool:
        """
        Check if a line is a comment or an empty line.

        Args:
            line (str): The line of code to check.
            language (str): The language of the code.

        Returns:
            bool: True if the line is a comment or an empty line, False otherwise
        """
        stripped_line = line.strip()
        comment_syntax = LanguageComment.get_comment_syntax(language)
        return not stripped_line or any(
            stripped_line.startswith(syntax) for syntax in comment_syntax
        )

    def get_commit_analysis(self) -> pd.DataFrame:
        """
        Analyzes the commits in the repository and returns a DataFrame with the following columns:
        - Date: The date of the commit.
        - Repository: The name of the repository.
        - Commit_hash: The hash of the commit.
        - Author: The author of the commit.
        - Language: The programming language of the modified file.
        - LOC_Added: The number of lines of code added.
        - LOC_Removed: The number of lines of code removed.
        - Net_LOC: The net lines of code (LOC_Added - LOC_Removed).

        Returns:
            pd.DataFrame: A DataFrame containing the analyzed commit data.
        """
        # Initialize the repository object for pydriller
        repository = Repository(
            self._repo_path,
            only_in_branch=self._branch_name,
            since=self._since,
            to=self._to,
            from_tag=self._from_tag,
            to_tag=self._to_tag,
            only_authors=self._authors,
            only_modifications_with_file_types=self._language_extensions,
            only_no_merge=False,
            histogram_diff=True,
            num_workers=1,
        )
        # Initialize the data frame to store the results
        data = pd.DataFrame(
            columns=[
                "Date",
                "Repository",
                "Commit_hash",
                "Author",
                "Language",
                "LOC_Added",
                "LOC_Removed",
                "Net_LOC",
            ]
        )

        # Traverse commits
        for commit in tqdm(repository.traverse_commits()):
            date = commit.committer_date.date()
            repository_name = GitRepoLOCAnalyzer.get_repository_name(self._repo_path)
            commit_hash = commit.hash
            author = commit.author.name

            # Traverse modified files
            for mod in tqdm(commit.modified_files):
                language = LanguageExtensions.get_language(mod.filename)

                # Calculate add LOC, delete LOC, net LOC
                # Parse diff, and calculate exclude comment lines and blank lines.
                loc_added = 0
                loc_removed = 0
                net_loc = 0
                if mod.diff_parsed:
                    for diff in mod.diff_parsed["added"]:
                        if not self.is_comment_or_empty_line(diff, language):
                            loc_added += 1
                    for diff in mod.diff_parsed["removed"]:
                        if not self.is_comment_or_empty_line(diff, language):
                            loc_removed += 1
                    net_loc = loc_added - loc_removed

                data.append(
                    {
                        "Date": date,
                        "Repository": repository_name,
                        "Commit_hash": commit_hash,
                        "Author": author,
                        "Language": language,
                        "LOC_Added": loc_added,
                        "LOC_Removed": loc_removed,
                        "Net_LOC": net_loc,
                    }
                )
        return data

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

    @classmethod
    def get_repository_name(cls, repo_path: Union[Path, str]) -> str:
        """
        Retrieves the repository name from the given local path or URL.

        If 'repo_path' is a Path object, it returns the directory name.
        If 'repo_path' is a string URL, it returns the last segment
        after '/' and removes ".git" if present.

        Args:
            repo_path (Union[Path, str]): The path or URL of the repository.

        Returns:
            str: The name of the repository.
        """
        # Check if repo_path is an instance of Path
        if isinstance(repo_path, Path):
            return repo_path.name

        # Assume repo_path is a string (URL), process accordingly
        return repo_path.rsplit("/", 1)[-1].removesuffix(".git")

    def valid_language_key(self, languages: list[str]) -> list[str]:
        """
        Validates the language keys and returns a list of valid language keys.

        Args:
            languages (list[str]): A list of language keys to validate.

        Returns:
            list[str]: A list of valid language keys.
        """

        def capitalize_words(words: str) -> str:
            """
            Capitalizes the first letter of each word in a given string.

            Args:
                words (str): A string containing words separated by spaces.

            Returns:
                str: A string with the first letter of each word capitalized.
            """

            return " ".join([word.capitalize() for word in words.split()])

        # Check if the language is in the language_to_extensions dictionary
        valid_languages: list[str] = []
        for lang in languages:
            if lang in LanguageExtensions.language_to_extensions:
                valid_languages.append(lang)
            else:
                # if the language is not in the dictionary, capitalize the first letter of each word
                capitalized_lang = capitalize_words(lang)
                if capitalized_lang in LanguageExtensions.language_to_extensions:
                    valid_languages.append(capitalized_lang)
        return valid_languages
