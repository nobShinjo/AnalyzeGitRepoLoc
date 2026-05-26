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
    get_commit_analysis(
        progress_callback: Callable[[str, int], None] | None = None
    ) -> pd.DataFrame:
        Analyzes the commits in the repository and returns a DataFrame with
        the analyzed commit data.
    save_cache() -> None:
    get_repository_name(repo_path: Union[Path, str]) -> str:
    get_repository_display_name(
        repo_path: Union[Path, str],
        repo_ref: Union[Path, str, None],
    ) -> str:
    valid_language_key(languages: list[str]) -> list[str]:

"""

import json
import os
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Union
from urllib.parse import urlparse

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
        exclude_dirs: list[str] = None,
        exclude_warning_dirs: list[str] | None = None,
        repo_ref: Union[Path, str, None] = None,
        show_progress: bool = True,
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
            exclude_dirs (list[str]): A list of directories to exclude from analysis.
            exclude_warning_dirs (list[str] | None): Excluded directories that should emit missing-path warnings.
            repo_ref (Union[Path, str, None]): Original repository path or URL for cache identity.
            show_progress (bool): Whether to show progress bars during analysis.

        Raises:
            OSError: If there is an error creating the cache or output directories.
        """
        # Initialize Git Repo object.
        self._repo_path = repo_path
        """ Git repository path """
        self._branch_name = branch_name
        """ Branch name to analyze """
        self._repo_ref = repo_ref if repo_ref is not None else repo_path
        """ Repository path or URL used for cache identity """

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
        self._language_extensions = LanguageExtensions.get_extensions(languages) or None
        """ Language extensions to filter commits """
        self._warnings: list[str] = []
        """Non-fatal analysis warnings collected for the caller."""
        self._exclude_dirs = [Path(repo_path).resolve() / d for d in exclude_dirs or []]
        """ List of directories to exclude from analysis """

        warning_dirs = exclude_dirs if exclude_warning_dirs is None else exclude_warning_dirs
        for raw_exclude_dir in warning_dirs or []:
            exclude_dir = Path(repo_path).resolve() / raw_exclude_dir
            if not exclude_dir.exists():
                self._warnings.append(
                    f"excluded path does not exist: {raw_exclude_dir}"
                )

        # Analyzed data
        self._commit_data = None
        """ DataFrame containing the analyzed commit data """
        self._latest_commit_hash = None
        """ Latest commit hash observed during analysis """
        self._cache_key = self._build_cache_key()
        """ Cache key for cache compatibility checks """
        self._cache_metadata = self._load_cache_metadata()
        """ Cache metadata loaded from disk """
        self._cache_commit_data = self.load_cache()
        """ DataFrame containing the cached commit data """
        self._show_progress = show_progress
        """ Whether to show progress bars during analysis """

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
        self._cache_commit_data = None
        if self._cache_path.exists() and self._cache_path.is_dir():
            for file in tqdm(
                self._cache_path.glob("**/*"),
                disable=not self._show_progress,
            ):
                if file.is_file():
                    try:
                        file.unlink()
                    except FileNotFoundError:
                        continue
                    except PermissionError:
                        print(
                            f"Warning: Unable to delete cache file: {file}",
                            file=sys.stderr,
                        )

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
        if not self._is_cache_metadata_compatible(self._cache_metadata):
            return None
        try:
            return pd.read_pickle(self._cache_path / "commit_data.pkl")
        except (FileNotFoundError, pd.errors.EmptyDataError):
            print("No cache file found. it does nothing, and continue.")
            return None

    def _build_repository(self) -> Repository:
        """
        Build a configured pydriller Repository instance.

        Returns:
            Repository: Configured repository traversal helper.
        """
        return Repository(
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

    def _count_commits_for_scan(self) -> int | None:
        """
        Count commits before PyDriller traversal when Git metadata is available.

        Returns:
            int | None: Commit count for the initial scan progress, or None if
            the count cannot be resolved safely.
        """
        try:
            repo = Repo(str(self._repo_path), search_parent_directories=True)
            pathspec = None
            worktree = repo.working_tree_dir
            if worktree is not None:
                try:
                    candidate = Path(self._repo_path).resolve()
                    root = Path(worktree).resolve()
                    if candidate != root and root in candidate.parents:
                        pathspec = str(candidate.relative_to(root))
                except (OSError, ValueError):
                    pathspec = None

            kwargs: dict[str, object] = {
                "rev": self._branch_name,
                "no_merges": True,
            }
            if self._since is not None:
                kwargs["since"] = self._since.isoformat()
            if self._to is not None:
                kwargs["until"] = self._to.isoformat()
            if self._authors and len(self._authors) == 1:
                kwargs["author"] = self._authors[0]
            if pathspec:
                kwargs["paths"] = pathspec

            return sum(1 for _ in repo.iter_commits(**kwargs))
        except (GitCommandError, OSError, TypeError, ValueError):
            return None

    def _get_commits(
        self,
        repository: Repository,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> list:
        """
        Collect commits from the repository traversal.

        Args:
            repository (Repository): Configured pydriller repository.
            progress_callback (Callable[[str, int], None] | None): Optional
                callback for commit scan progress events.

        Returns:
            list: List of commit objects.
        """
        commits = []
        scan_total = self._count_commits_for_scan()
        if progress_callback is not None and scan_total is not None:
            try:
                progress_callback("scan_total", scan_total)
            except (AttributeError, EOFError, OSError, TypeError, ValueError):
                pass
        for commit in tqdm(
            repository.traverse_commits(),
            desc="Getting commits",
            total=scan_total,
            unit="commit",
            disable=not self._show_progress,
        ):
            commits.append(commit)
            if progress_callback is not None:
                try:
                    progress_callback("scan_advance", 1)
                except (AttributeError, EOFError, OSError, TypeError, ValueError):
                    continue
        return commits

    @staticmethod
    def _find_commit_index(commits: list, target_hash: str | None) -> int | None:
        """
        Find the index of a commit hash within a list of commits.

        Args:
            commits (list): Commit list.
            target_hash (str | None): Commit hash to locate.

        Returns:
            int | None: Index when found, otherwise None.
        """
        if not target_hash:
            return None
        for index, commit in enumerate(commits):
            if commit.hash == target_hash:
                return index
        return None

    def _prepare_cache_state(
        self, commits: list
    ) -> tuple[list, dict[str, list[dict]] | None, bool]:
        """
        Prepare cache state for incremental analysis.

        Args:
            commits (list): Commit list.

        Returns:
            tuple[list, dict | None, bool]: Commits to analyze, cache lookup, and
            whether to append cached results after analysis.
        """
        if self._cache_commit_data is None:
            return commits, None, False
        cache_resume_hash = (
            self._cache_metadata.get("last_commit_hash")
            if self._cache_metadata
            else None
        )
        resume_index = self._find_commit_index(commits, cache_resume_hash)
        if resume_index is None:
            return commits, self._build_cache_lookup(self._cache_commit_data), False
        return commits[:resume_index], None, True

    @staticmethod
    def _apply_cached_commit(
        commit_hash: str,
        cache_lookup: dict[str, list[dict]] | None,
        commit_data_list: list[dict],
    ) -> bool:
        """
        Append cached rows for a commit when available.

        Args:
            commit_hash (str): Commit hash to check.
            cache_lookup (dict | None): Cache lookup.
            commit_data_list (list[dict]): Aggregated commit data rows.

        Returns:
            bool: True when cached rows were appended.
        """
        if cache_lookup is None:
            return False
        cached_rows = cache_lookup.get(commit_hash)
        if not cached_rows:
            return False
        commit_data_list.extend(cached_rows)
        return True

    def _should_skip_modification(self, mod: object, language: str) -> bool:
        """
        Determine whether a file modification should be skipped.

        Args:
            mod (object): Modification entry from pydriller.
            language (str): Language name.

        Returns:
            bool: True when the modification should be skipped.
        """
        if language == "Unknown":
            return True
        if (
            self._exclude_dirs
            and getattr(mod, "new_path", None)
            and any(
                (Path(self._repo_path) / mod.new_path).resolve().is_relative_to(d)
                for d in self._exclude_dirs
            )
        ):
            return True
        if self._languages and language not in self._languages:
            return True
        return False

    @staticmethod
    def _create_progress_tracker(
        progress_callback: Callable[[str, int], None] | None,
        total_commits: int,
    ) -> tuple[Callable[[int], None], Callable[[], None]]:
        """
        Build a progress tracker for commit analysis.
        """
        if progress_callback is None:
            return (lambda _step: None), (lambda: None)

        def safe_progress(kind: str, value: int) -> None:
            try:
                progress_callback(kind, value)
            except (AttributeError, EOFError, OSError, TypeError, ValueError):
                # Ignore callback errors to avoid breaking analysis.
                return

        safe_progress("total", total_commits)
        update_interval = max(1, total_commits // 100)
        pending_updates = 0

        def record(step: int) -> None:
            nonlocal pending_updates
            pending_updates += step
            if pending_updates >= update_interval:
                safe_progress("advance", pending_updates)
                pending_updates = 0

        def flush() -> None:
            if pending_updates:
                safe_progress("advance", pending_updates)

        return record, flush

    def _append_commit_rows(
        self,
        commit: object,
        repository_name: str,
        cache_lookup: dict[str, list[dict]] | None,
        commit_data_list: list[dict],
    ) -> bool:
        """
        Append commit data rows for a single commit.
        """
        commit_hash = commit.hash
        if self._apply_cached_commit(commit_hash, cache_lookup, commit_data_list):
            return True
        commit_datetime = commit.committer_date
        commit_author = commit.author.name
        for mod in commit.modified_files:
            language = LanguageExtensions.get_language(mod.filename)
            if self._should_skip_modification(mod, language):
                continue

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
        return False

    def get_commit_analysis(
        self, progress_callback: Callable[[str, int], None] | None = None
    ) -> pd.DataFrame:
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

        Args:
            progress_callback (Callable[[str, int], None] | None): Optional
                callback that receives progress events. The callback is called
                with ("total", commit_count) once and ("advance", step) as
                commits are processed.

        Returns:
            pd.DataFrame: A DataFrame containing the analyzed commit data.
        """

        repository = self._build_repository()

        # temporary list to store commit data
        commit_data_list = []
        commits = self._get_commits(repository, progress_callback=progress_callback)
        self._latest_commit_hash = commits[0].hash if commits else None
        (
            commits_to_analyze,
            cache_lookup,
            use_cache_resume,
        ) = self._prepare_cache_state(commits)

        total_commits = len(commits_to_analyze)
        record_progress, flush_progress = self._create_progress_tracker(
            progress_callback,
            total_commits,
        )
        repository_name = GitRepoLOCAnalyzer.get_repository_display_name(
            repo_path=self._repo_path,
            repo_ref=self._repo_ref,
        )

        # Traverse commits
        for commit in tqdm(
            commits_to_analyze,
            desc="Analyzing commits",
            total=len(commits_to_analyze),
            unit="commit",
            disable=not self._show_progress,
        ):
            self._append_commit_rows(
                commit,
                repository_name,
                cache_lookup,
                commit_data_list,
            )
            record_progress(1)
        flush_progress()
        if use_cache_resume and self._cache_commit_data is not None:
            commit_data_list.extend(self._cache_commit_data.to_dict("records"))
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
        self._write_cache_metadata()

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

        # Handle scp-style URLs like git@host:org/repo.git
        if "@" in repo_path and ":" in repo_path and "://" not in repo_path:
            repo_path = repo_path.split(":", 1)[1]
        # Assume repo_path is a string (URL), process accordingly
        return repo_path.rsplit("/", 1)[-1].removesuffix(".git")

    @classmethod
    def get_repository_display_name(
        cls,
        repo_path: Union[Path, str],
        repo_ref: Union[Path, str, None],
    ) -> str:
        """
        Get the human-readable repository name for reports.

        Args:
            repo_path (Union[Path, str]): Local repository path used for analysis.
            repo_ref (Union[Path, str, None]): Original repository path or URL.

        Returns:
            str: Repository name for display and report data.
        """
        if repo_ref is None:
            return cls.get_repository_name(repo_path)
        return cls.get_repository_name(repo_ref)

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

    @staticmethod
    def _looks_like_url(value: str) -> bool:
        """
        Determine whether a string looks like a Git URL.

        Args:
            value (str): Input value to inspect.

        Returns:
            bool: True when the value looks like a URL.
        """
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https", "ssh", "git"}:
            return True
        return value.startswith("git@") and ":" in value

    @staticmethod
    def _strip_url_credentials(value: str) -> str:
        """
        Strip user info from HTTPS URLs when present.

        Args:
            value (str): URL string.

        Returns:
            str: URL without embedded credentials.
        """
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            netloc = parsed.hostname
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            return parsed._replace(netloc=netloc).geturl()
        return value

    def _normalize_repo_ref(self) -> str:
        """
        Normalize the repository identifier for cache keys.

        Returns:
            str: Normalized repo identity string.
        """
        if isinstance(self._repo_ref, Path):
            return self._repo_ref.resolve().as_posix()
        if isinstance(self._repo_ref, str):
            value = self._repo_ref.strip()
            if self._looks_like_url(value):
                return self._strip_url_credentials(value)
            return Path(value).resolve().as_posix()
        return str(self._repo_ref)

    @staticmethod
    def _normalize_cache_list(values: list[str] | None) -> list[str]:
        """
        Normalize list values for cache keys by trimming and sorting.

        Args:
            values (list[str] | None): Raw list values.

        Returns:
            list[str]: Normalized list.
        """
        if not values:
            return []
        return sorted([item.strip() for item in values if item and item.strip()])

    @staticmethod
    def _normalize_cache_date(value: datetime | None) -> str | None:
        """
        Normalize datetime values into ISO format for cache keys.

        Args:
            value (datetime | None): Datetime value.

        Returns:
            str | None: ISO formatted string or None.
        """
        if value is None:
            return None
        return value.isoformat()

    def _normalize_cache_paths(self, paths: list[Path] | None) -> list[str]:
        """
        Normalize path list values for cache keys.

        Args:
            paths (list[Path] | None): Path list.

        Returns:
            list[str]: Sorted list of normalized paths.
        """
        if not paths:
            return []
        normalized = [path.resolve().as_posix() for path in paths]
        return sorted(normalized)

    def _build_cache_key(self) -> dict[str, object]:
        """
        Build the cache key based on repository and filter inputs.

        Returns:
            dict[str, object]: Cache key dictionary.
        """
        return {
            "repo": self._normalize_repo_ref(),
            "branch": self._branch_name,
            "since": self._normalize_cache_date(self._since),
            "until": self._normalize_cache_date(self._to),
            "languages": self._normalize_cache_list(self._languages),
            "authors": self._normalize_cache_list(self._authors),
            "exclude_dirs": self._normalize_cache_paths(self._exclude_dirs),
        }

    def _load_cache_metadata(self) -> dict | None:
        """
        Load cache metadata from disk if present.

        Returns:
            dict | None: Parsed metadata, or None when unavailable.
        """
        metadata_path = self._cache_path / "cache_metadata.json"
        try:
            with open(metadata_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            return None

    def _is_cache_metadata_compatible(self, metadata: dict | None) -> bool:
        """
        Check whether cache metadata matches the current cache key/version.

        Args:
            metadata (dict | None): Cached metadata.

        Returns:
            bool: True when compatible.
        """
        if not metadata:
            return False
        if metadata.get("version") != 1:
            return False
        return metadata.get("key") == self._cache_key

    def _write_cache_metadata(self) -> None:
        """
        Persist cache metadata for later reuse.
        """
        metadata = {
            "version": 1,
            "key": self._cache_key,
            "last_commit_hash": self._latest_commit_hash,
            "saved_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        metadata_path = self._cache_path / "cache_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=2)

    @staticmethod
    def _build_cache_lookup(cache_data: pd.DataFrame) -> dict[str, list[dict]]:
        """
        Build a lookup of cached rows by commit hash.

        Args:
            cache_data (pd.DataFrame): Cached commit data.

        Returns:
            dict[str, list[dict]]: Commit hash to cached row mapping.
        """
        lookup: dict[str, list[dict]] = {}
        for row in cache_data.to_dict("records"):
            lookup.setdefault(row["Commit_hash"], []).append(row)
        return lookup
