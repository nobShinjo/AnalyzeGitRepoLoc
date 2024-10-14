"""
This module provides the `GitRepoLOCAnalyzer` class for analyzing lines of code (LOC)
 in a Git repository.

Classes:
    GitRepoLOCAnalyzer: A class for analyzing LOC in a Git repository.

Functions:
    make_output_dir(output_dir: Path) -> Path:
    clear_cache_files():
        Deletes all files located in the directory specified by the `_cache_path` attribute.
    is_branch_exists(repo_path: PathLike, branch_name: str) -> bool:
        Checks if a branch exists in the given Git repository.
    is_comment_or_empty_line(line: str, language: str) -> bool:
        Checks if a line is a comment or an empty line.
    load_cache() -> pd.DataFrame:
        Loads the cached commit data from the cache directory.
    get_commit_analysis() -> pd.DataFrame:
        Analyzes the commits in the repository and returns a DataFrame with 
        the analyzed commit data.
    save_cache() -> None:
    get_repository_name(repo_path: Union[Path, str]) -> str:
    valid_language_key(languages: list[str]) -> list[str]:

"""

import os
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
        self._language_extensions = LanguageExtensions.get_extensions(languages)
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
            output_dir.mkdir(parents=True, exist_ok=True)
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
        """
        try:
            repo = Repo(repo_path)
            return branch_name in repo.heads
        except (GitCommandError, AttributeError):
            return False

    @classmethod
    def is_comment_or_empty_line(cls, line: str, language: str) -> bool:
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
        if not comment_syntax:
            return not stripped_line
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
        - NLOC_Deleted: The number of net lines of code deleted.
        - NLOC: The net lines of code (NLOC_Added - NLOC_Deleted).

        Returns:
            pd.DataFrame: A DataFrame containing the analyzed commit data.
        """
        # Initialize the repository object for pydriller
        repository = Repository(
            str(self._repo_path),
            only_in_branch=self._branch_name,
            since=self._since,
            to=self._to,
            from_tag=self._from_tag,
            to_tag=self._to_tag,
            only_authors=self._authors,
            only_modifications_with_file_types=self._language_extensions,
            only_no_merge=True,
            histogram_diff=True,
            num_workers=os.cpu_count(),
        )

        # temporary list to store commit data
        commit_data_list = []
        commits = list(
            tqdm(repository.traverse_commits(), desc="Getting commits", unit="commit")
        )
        total_commits = len(commits)

        # Traverse commits
        for commit in tqdm(
            commits,
            desc="Analyzing commits",
            total=total_commits,
            unit="commit",
        ):
            commit_datetime = commit.committer_date
            repository_name = GitRepoLOCAnalyzer.get_repository_name(self._repo_path)
            commit_hash = commit.hash
            commit_author = commit.author.name

            # Skip if the commit is already analyzed
            if self._cache_commit_data is not None:
                # Check for the presence of commit_hash in the "Commit_hash" column
                # of the cached commit data. If found, append the matching rows to
                # the commit_data_list and continue to the next commit.
                matching_rows = self._cache_commit_data[
                    self._cache_commit_data["Commit_hash"] == commit_hash
                ]
                if not matching_rows.empty:
                    commit_data_list.extend(matching_rows.to_dict("records"))
                    continue

            # Traverse modified files
            for mod in commit.modified_files:
                # Get the programming language of the modified file
                language = LanguageExtensions.get_language(mod.filename)
                if language == "Unknown":
                    continue

                # Skip if the file is not in the specified language
                if self._languages and language not in self._languages:
                    continue

                # Calculate add LOC, delete LOC, net LOC
                # NOTE: diff_parsed is a list of tuples (line_number, line)
                nloc_added = sum(
                    1
                    for _, diff in mod.diff_parsed.get("added", [])
                    if not self.is_comment_or_empty_line(diff, language)
                )
                nloc_deleted = sum(
                    1
                    for _, diff in mod.diff_parsed.get("deleted", [])
                    if not self.is_comment_or_empty_line(diff, language)
                )
                nloc = nloc_added - nloc_deleted

                commit_data_list.append(
                    {
                        "Datetime": commit_datetime,
                        "Repository": repository_name,
                        "Branch": self._branch_name,
                        "Commit_hash": commit_hash,
                        "Author": commit_author,
                        "Language": language,
                        "NLOC_Added": nloc_added,
                        "NLOC_Deleted": nloc_deleted,
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
                "NLOC_Deleted",
                "NLOC",
            ],
        )
        # Column type conversion
        commit_data["Datetime"] = pd.to_datetime(commit_data["Datetime"], utc=True)
        commit_data["Repository"] = commit_data["Repository"].astype("string")
        commit_data["Branch"] = commit_data["Branch"].astype("string")
        commit_data["Commit_hash"] = commit_data["Commit_hash"].astype("string")
        commit_data["Author"] = commit_data["Author"].astype("string")
        commit_data["Language"] = commit_data["Language"].astype("string")
        commit_data["NLOC_Added"] = commit_data["NLOC_Added"].astype("int")
        commit_data["NLOC_Deleted"] = commit_data["NLOC_Deleted"].astype("int")
        commit_data["NLOC"] = commit_data["NLOC"].astype("int")

        self._commit_data = commit_data
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
