"""

"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Union

import pandas as pd
from git import GitCommandError, PathLike, Repo
from pydriller import Repository
from tqdm import tqdm

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

        Raises:
            OSError: If there is an error creating the cache or output directories.
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

        # Analyzed data
        self._commit_data = None
        """ DataFrame containing the analyzed commit data """
        self._cache_commit_data = self.load_cache()
        """ DataFrame containing the cached commit data """

    def make_output_dir(self, output_dir: Path) -> Path:
        """
        Creates the specified output directory, including any necessary parent directories.

        Args:
            output_dir (Path): The path of the directory to create.

        Returns:
            Path: The path of the created directory.

        Raises:
            OSError: If the directory cannot be created.
        """
        try:
            output_dir.mkdir(parents=True, exports=True)
        except OSError as ex:
            print(f"Error creating directory: {str(ex)})", file=sys.stderr)
            raise
        return output_dir

    def clear_cache_files(self):
        """
        Delete all files located in the directory specified by the `_cache_path` attribute.

        This method checks if `_cache_path` exists and is a directory. If so,
        it proceeds to iterate through all files within this directory (including
        subdirectories) and deletes each file.

        Raises:
            FileNotFoundError: If the cache directory does not exist.
        """
        try:
            if self._cache_path.exists() and self._cache_path.is_dir():
                for file in tqdm(self._cache_path.glob("**/*")):
                    if file.is_file():
                        file.unlink()
        except FileNotFoundError as ex:
            raise

    def is_branch_exists(self, repo_path: PathLike, branch_name: str) -> bool:
        """
        Check if a branch exists in the given Git repository.

        Args:
            repo_path (PathLike): The file system path to the Git repository.
            branch_name (str): The name of the branch to check for existence.

        Returns:
            bool: True if the branch exists, False otherwise.
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

    def load_cache(self) -> pd.DataFrame:
        """
        Load the cached commit data from the cache directory.

        This method reads the cached commit data from the pickle file located
        at the specified cache path. If the file does not exist, it does nothing.

        Returns:
            pd.DataFrame: The cached commit data, if available, otherwise an empty DataFrame.
        """
        try:
            return pd.read_pickle(self._cache_path / "commit_data.pkl")
        except (FileNotFoundError, pd.errors.EmptyDataError):
            print("No cache file found. it does nothing, and continue.")
            return None

    def get_commit_analysis(self) -> pd.DataFrame:
        """
        Analyzes the commits in the repository and returns a DataFrame with the following columns:
        - Datetime: The date of the commit.
        - Repository: The name of the repository.
        - Commit_hash: The hash of the commit.
        - Author: The author of the commit.
        - Language: The programming language of the modified file.
        - NLOC_Added: The number of net lines of code added.
        - NLOC_Removed: The number of net lines of code removed.
        - NLOC: The net lines of code (NLOC_Added - NLOC_Removed).

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

        # temporary list to store commit data
        commit_data_list = []
        # Traverse commits
        for commit in tqdm(
            repository.traverse_commits(),
            desc="Commits",
        ):
            commit_datetime = commit.committer_date
            repository_name = GitRepoLOCAnalyzer.get_repository_name(self._repo_path)
            commit_hash = commit.hash
            commit_author = commit.author.name

            # Skip if the commit is already analyzed
            if self._cache_commit_data is not None:
                # Check for the presence of commit_hash in the "Commit_hash" column
                matching_rows = self._cache_commit_data[
                    self._cache_commit_data["Commit_hash"] == commit_hash
                ]

                # Convert matching rows to a list of dictionaries and extend the target list
                if not matching_rows.empty:
                    commit_data_list.extend(matching_rows.to_dict("records"))
                    continue

            # Traverse modified files
            for mod in tqdm(
                commit.modified_files,
                desc=f"Files in {commit_hash[:7]}",
                leave=False,
            ):
                language = LanguageExtensions.get_language(mod.filename)
                if language == "Unknown":
                    continue

                # Calculate add LOC, delete LOC, net LOC
                # Calculate add LOC, delete LOC, net LOC
                nloc_added = sum(
                    1
                    for diff in mod.diff_parsed.get("added", [])
                    if not self.is_comment_or_empty_line(diff, language)
                )
                nloc_removed = sum(
                    1
                    for diff in mod.diff_parsed.get("removed", [])
                    if not self.is_comment_or_empty_line(diff, language)
                )
                nloc = nloc_added - nloc_removed

                commit_data_list.append(
                    {
                        "Datetime": commit_datetime,
                        "Repository": repository_name,
                        "Branch": self._branch_name,
                        "Commit_hash": commit_hash,
                        "Author": commit_author,
                        "Language": language,
                        "NLOC_Added": nloc_added,
                        "NLOC_Removed": nloc_removed,
                        "NLOC": nloc,
                    }
                )
        # Create DataFrame from list in a single operation
        commit_data = pd.DataFrame(
            commit_data_list,
            columns=[
                "Datetime",
                "Repository",
                "Branch",
                "Commit_hash",
                "Author",
                "Language",
                "NLOC_Added",
                "NLOC_Removed",
                "NLOC",
            ],
        )
        # Column type conversion
        commit_data["Datetime"] = pd.to_datetime(commit_data["Datetime"])
        commit_data["Repository"] = commit_data["Repository"].astype("string")
        commit_data["Branch"] = commit_data["Branch"].astype("string")
        commit_data["Commit_hash"] = commit_data["Commit_hash"].astype("string")
        commit_data["Author"] = commit_data["Author"].astype("string")
        commit_data["Language"] = commit_data["Language"].astype("string")
        commit_data["NLOC_Added"] = commit_data["NLOC_Added"].astype("int")
        commit_data["NLOC_Removed"] = commit_data["NLOC_Removed"].astype("int")
        commit_data["NLOC"] = commit_data["NLOC"].astype("int")

        return commit_data

    def save_cache(self) -> None:
        """
        Saves the commit data to a cache file.

        This method serializes the commit data and saves it to a pickle file
        located at the specified cache path. If there is no commit data available,
        it raises a ValueError.

        Raises:
            ValueError: If there is no commit data to save.
        """
        if self._commit_data is None:
            raise ValueError("No data to save. Run get_commit_analysis() first.")

        self._commit_data.to_pickle(self._cache_path / "commit_data.pkl")

    # def create_charts(
    #     self,
    #     sub_title: str,
    # ):
    #     """
    #     Creates charts using the provided trend and summation data.

    #     This method takes a trend dataframe and a summation dataframe,
    #     builds a chart using the internal _chart_builder.
    #     Args:
    #         language_trend_data (pd.DataFrame):
    #             A pandas DataFrame containing the trend data of LOC by language.
    #         author_trend_data (pd.DataFrame):
    #             A pandas DataFrame containing the trend data of LOC by author.
    #         sum_data (pd.DataFrame): A pandas DataFrame that contains the summary data.
    #         output_path (Path): The path to save the chart HTML file.
    #         interval (str): The interval to use for formatting the x-axis ticks.
    #                         Should be one of 'daily', 'weekly', or 'monthly'.
    #         sub_title (str): The sub-title to include in the chart title.
    #     """

    #     # Combine two charts
    #     self._chart = make_subplots(
    #         rows=2,
    #         cols=1,
    #         shared_xaxes=True,
    #         subplot_titles=("Language Trend", "Author Trend"),
    #         vertical_spacing=0.1,
    #         specs=[[{"secondary_y": True}], [{"secondary_y": True}]],
    #     )

    #     # Add traces from language_trend_chart
    #     for trace in language_trend_chart["data"]:
    #         self._chart.add_trace(trace, row=1, col=1)

    #     # Add traces from author_trend_chart
    #     for trace in author_trend_chart["data"]:
    #         self._chart.add_trace(trace, row=2, col=1)

    #     # Update layout
    #     self._chart.update_xaxes(
    #         showline=True,
    #         linewidth=1,
    #         linecolor="grey",
    #         color="black",
    #         gridcolor="lightgrey",
    #         gridwidth=0.5,
    #         title_text="Date",
    #         title_font_size=18,
    #         tickfont_size=14,
    #         tickangle=-45,
    #         tickformat=language_trend_chart["layout"]["xaxis"]["tickformat"],
    #         automargin=True,
    #     )
    #     self._chart.update_yaxes(
    #         secondary_y=False,
    #         showline=True,
    #         linewidth=1,
    #         linecolor="grey",
    #         color="black",
    #         gridcolor="lightgrey",
    #         gridwidth=0.5,
    #         title_text="LOC",
    #         title_font_size=18,
    #         tickfont_size=14,
    #         range=[0, None],
    #         autorange="max",
    #         rangemode="tozero",
    #         automargin=True,
    #         spikethickness=1,
    #         spikemode="toaxis+across",
    #     )
    #     self._chart.update_yaxes(
    #         secondary_y=True,
    #         showline=True,
    #         linewidth=1,
    #         linecolor="grey",
    #         color="black",
    #         gridcolor="lightgrey",
    #         gridwidth=0.5,
    #         title_text="Difference of LOC",
    #         title_font_size=18,
    #         tickfont_size=14,
    #         range=[0, None],
    #         autorange="max",
    #         rangemode="tozero",
    #         automargin=True,
    #         spikethickness=1,
    #         spikemode="toaxis+across",
    #         overlaying="y",
    #         side="right",
    #     )
    #     chat_title = f"LOC trend by Language and Author - {sub_title}"
    #     self._chart.update_layout(
    #         font_family="Open Sans",
    #         plot_bgcolor="white",
    #         title={
    #             "text": chat_title,
    #             "x": 0.5,
    #             "xanchor": "center",
    #             "font_size": 20,
    #         },
    #         xaxis={"dtick": "M1"},
    #         legend_title_font_size=14,
    #         legend_font_size=14,
    #     )

    #     self._chart.show()

    # def save_charts(self, output_path: Path) -> None:
    #     """
    #     Saves the generated charts to HTML format.

    #     The file is saved to the path specified by _output_path with the filename 'report.html'.
    #     It's expected that the _chart attribute is already populated with a chart object.

    #     Args:
    #         output_path (Path): The path to save the chart HTML file.
    #     """
    #     if self._chart is not None:
    #         self._chart.write_html(output_path / "report.html")

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
