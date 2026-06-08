"""Repository analysis orchestration.

Description:
    Executes repository analysis runs, manages cache-aware repository
    preparation, and coordinates progress reporting. The module keeps the
    runtime pipeline cohesive while allowing `utils.py` to remain a thin
    compatibility layer.
Functions:
    analyze_git_repositories:
        Analyze all configured repositories and return their LOC dataframes.
    save_repository_branch_info:
        Persist repository and branch selections for the current run.
    analyze_trends:
        Aggregate LOC data into interval-based trend tables.
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from multiprocessing import Manager
from multiprocessing.managers import SyncManager
from pathlib import Path
from threading import Event, Thread
from dataclasses import dataclass
from typing import Callable, cast

import pandas as pd  # pyright: ignore[reportMissingImports]
from tqdm import tqdm  # pyright: ignore[reportMissingModuleSource]

from analyze_git_repo_loc.analysis.exclude_templates import (
    ExcludeRecommendation,
    ExcludeTemplateMode,
    build_exclude_recommendation,
    load_exclude_templates,
    normalize_exclude_template_mode,
)
from analyze_git_repo_loc.analysis.git_repo_loc_analyzer import (
    GitRepoLOCAnalyzer,
    GitRepoLOCAnalyzerOptions,
)
from analyze_git_repo_loc.colored_console_printer import ColoredConsolePrinter
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.remote.remote_repos import RemoteRepoManager
from analyze_git_repo_loc.repo_progress import (
    REPO_EVENT_ADVANCE,
    REPO_EVENT_FINISH,
    REPO_EVENT_SCAN_ADVANCE,
    REPO_EVENT_SCAN_TOTAL,
    REPO_EVENT_STOP,
    REPO_EVENT_TOTAL,
    REPO_PROGRESS_BAR_FORMAT,
    REPO_PROGRESS_LABEL_WIDTH,
    ProgressQueue,
    emit_repo_progress,
    format_repo_progress_description,
    start_repo_progress_listener,
    truncate_repo_label,
)

_REMOTE_REPO_MANAGER = RemoteRepoManager()


def _resolve_analysis_repo_path(
    repo_path: Path | str,
    branch_name: str,
    cache_dir: Path,
    *,
    update_remote: bool = True,
) -> Path | str:
    """Resolve the analysis path for a repository, cloning if needed."""
    if isinstance(repo_path, str) and _REMOTE_REPO_MANAGER.is_git_url(repo_path):
        return _REMOTE_REPO_MANAGER.prepare_remote_repository(
            repo_url=repo_path,
            branch_name=branch_name,
            cache_dir=cache_dir,
            update_remote=update_remote,
        )
    return repo_path


def _apply_include_subpath(
    analysis_repo_path: Path | str,
    include_subpath: str | Path | None,
) -> Path | str:
    """Apply a repository-root-relative include subpath when configured."""
    if include_subpath is None or include_subpath == "":
        return analysis_repo_path
    subpath = Path(include_subpath)
    if subpath == Path("."):
        return analysis_repo_path
    if subpath.is_absolute():
        raise ValueError("include_subpath must be repository-root-relative.")
    root = Path(analysis_repo_path).resolve()
    candidate = (root / subpath).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("include_subpath must resolve within repository root.")
    return candidate


def _create_analyzer(
    *,
    analysis_repo_path: Path | str,
    repo_ref: Path | str,
    branch_name: str,
    cache_dir: Path,
    output_dir: Path,
    since: datetime | None,
    until: datetime | None,
    authors: list[str] | None,
    languages: list[str] | None,
    exclude_dirs: list[str] | None,
    exclude_warning_dirs: list[str] | None,
    show_progress: bool,
) -> GitRepoLOCAnalyzer:
    """Build a `GitRepoLOCAnalyzer` with common arguments."""
    return GitRepoLOCAnalyzer(
        repo_path=analysis_repo_path,
        branch_name=branch_name,
        cache_dir=cache_dir,
        output_dir=output_dir,
        options=GitRepoLOCAnalyzerOptions(
            since=since,
            to=until,
            authors=authors,
            languages=languages,
            exclude_dirs=exclude_dirs,
            exclude_warning_dirs=exclude_warning_dirs,
        ),
        repo_ref=repo_ref,
        show_progress=show_progress,
    )


def _maybe_clear_cache(
    *,
    analyzer: GitRepoLOCAnalyzer,
    console: ColoredConsolePrinter | None,
    clear_cache: bool,
    show_progress: bool,
) -> None:
    """Clear cache files when requested."""
    if not clear_cache:
        return
    if show_progress and console is not None:
        console.print_h1(f"# {tr('progress.remove_cache')}")
    analyzer.clear_cache_files()
    if show_progress and console is not None:
        console.print_ok(up=2, forward=50)


def _ensure_repo_output_dir(output_dir: Path, repository_name: str) -> Path:
    """Ensure the output directory exists for a repository."""
    repo_output_dir = output_dir / repository_name
    repo_output_dir.mkdir(parents=True, exist_ok=True)
    return repo_output_dir


def save_repository_branch_info(repo_paths, output_file: Path) -> None:
    """Save repository and branch information to a text file."""
    with open(output_file, "w", encoding="utf-8") as file_handle:
        file_handle.write(
            "\n".join(
                [f"repository: {entry[0]}, branch: {entry[1]}" for entry in repo_paths]
            )
        )


def analyze_trends(
    category_column: str,
    interval: str,
    loc_data: pd.DataFrame,
    analysis_data: pd.DataFrame,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Analyze LOC trends and optionally save the aggregated CSV."""
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


def _resolve_exclude_dirs(
    args: argparse.Namespace,
    exclude_dirs: list[str] | None,
) -> list[str] | None:
    """Resolve manually configured excluded directories, preferring CLI overrides."""
    if args.exclude_dirs is not None:
        return args.exclude_dirs
    return exclude_dirs


def _resolve_exclude_template_mode(
    args: argparse.Namespace,
    repo_mode: str | None,
) -> ExcludeTemplateMode:
    """Resolve repository-level exclude template mode with settings fallback."""
    if repo_mode is not None:
        return normalize_exclude_template_mode(repo_mode)
    return normalize_exclude_template_mode(
        getattr(args, "exclude_template_mode", "auto")
    )


def _resolve_exclude_template_names(
    args: argparse.Namespace,
    repo_template_names: list[str] | None,
) -> list[str] | None:
    """Resolve repository-level selected exclude templates with settings fallback."""
    if repo_template_names is not None:
        return repo_template_names
    return getattr(args, "exclude_template_names", None)


def _build_exclude_recommendation_for_repo(
    *,
    analysis_repo_path: Path | str,
    manual_excludes: list[str] | None,
    template_mode: ExcludeTemplateMode,
    template_names: list[str] | None,
    template_files: list[str] | None,
) -> ExcludeRecommendation:
    """Build repository exclude recommendations after path resolution."""
    templates = load_exclude_templates(template_files)
    return build_exclude_recommendation(
        Path(analysis_repo_path),
        manual_excludes=manual_excludes,
        selected_template_names=template_names,
        mode=template_mode,
        templates=templates,
    )


def _build_exclude_summary(
    *,
    repository_name: str,
    recommendation: ExcludeRecommendation,
) -> dict[str, object]:
    """Build display metadata for repository exclude template decisions."""
    templates = [
        item.template.display_name
        for item in recommendation.detected_templates
        if item.template is not None
    ]
    return {
        "repository": repository_name,
        "mode": recommendation.mode,
        "templates": templates,
        "excluded_paths": list(recommendation.paths),
        "template_paths": list(recommendation.template_paths),
        "manual_paths": list(recommendation.manual_paths),
        "selected_template_names": list(recommendation.selected_template_names),
    }


@dataclass(frozen=True)
class _SingleRepositoryAnalysisRequest:
    index: int
    repo_path: Path | str
    branch_name: str
    exclude_dirs: list[str] | None
    include_subpath: str | Path | None
    exclude_template_mode: ExcludeTemplateMode
    exclude_template_names: list[str] | None
    exclude_template_files: list[str] | None
    output_dir: Path
    since: datetime | None
    until: datetime | None
    authors: list[str] | None
    languages: list[str] | None
    clear_cache: bool
    show_progress: bool
    update_remote_cache: bool = True
    progress_queue: ProgressQueue | None = None


@dataclass(frozen=True)
class _SingleRepositoryAnalysisDeps:
    resolve_analysis_repo_path: Callable[..., Path | str] = _resolve_analysis_repo_path
    apply_include_subpath: Callable[..., Path | str] = _apply_include_subpath
    build_exclude_recommendation_for_repo: Callable[
        ..., ExcludeRecommendation
    ] = _build_exclude_recommendation_for_repo
    build_exclude_summary: Callable[..., dict[str, object]] = _build_exclude_summary
    create_analyzer: Callable[..., object] = _create_analyzer
    maybe_clear_cache: Callable[..., None] = _maybe_clear_cache
    ensure_repo_output_dir: Callable[[Path, str], Path] = _ensure_repo_output_dir


def _unpack_repo_entry(
    repo_entry: tuple,
) -> tuple[
    Path | str, str, list[str] | None, str | Path | None, str | None, list[str] | None
]:
    """Normalize repository entries to include path and exclude template overrides."""
    if len(repo_entry) == 3:
        repo_path, branch_name, exclude_dirs = repo_entry
        return repo_path, branch_name, exclude_dirs, None, None, None
    if len(repo_entry) == 4:
        repo_path, branch_name, exclude_dirs, include_subpath = repo_entry
        return repo_path, branch_name, exclude_dirs, include_subpath, None, None
    if len(repo_entry) == 6:
        (
            repo_path,
            branch_name,
            exclude_dirs,
            include_subpath,
            template_mode,
            template_names,
        ) = repo_entry
        return (
            repo_path,
            branch_name,
            exclude_dirs,
            include_subpath,
            template_mode,
            template_names,
        )
    raise ValueError("Repository entries must contain 3, 4, or 6 values.")


def _analyze_single_repository(
    request: _SingleRepositoryAnalysisRequest,
    deps: _SingleRepositoryAnalysisDeps = _SingleRepositoryAnalysisDeps(),
) -> tuple[int, str, pd.DataFrame, list[str], dict[str, object]]:
    """Analyze a single repository and return its index, data, and metadata."""
    if request.show_progress:
        os.environ.pop("ANALYZE_GIT_REPO_LOC_LOG_AUTH", None)
    else:
        os.environ["ANALYZE_GIT_REPO_LOC_LOG_AUTH"] = "0"
    console = ColoredConsolePrinter() if request.show_progress else None
    repository_name = GitRepoLOCAnalyzer.get_repository_name(request.repo_path)
    emit_repo_progress(
        request.progress_queue,
        "start",
        request.index,
        repository_name,
    )
    if request.show_progress and console is not None:
        console.print_h1("\n")
        console.print_h1(
            "# "
            + tr(
                "run.section.repository_analysis",
                repository=repository_name,
                branch=request.branch_name,
            ),
        )
    try:
        analysis_repo_path = deps.resolve_analysis_repo_path(
            repo_path=request.repo_path,
            branch_name=request.branch_name,
            cache_dir=request.output_dir / ".cache",
            update_remote=request.update_remote_cache,
        )
        analysis_repo_path = deps.apply_include_subpath(
            analysis_repo_path,
            request.include_subpath,
        )
        exclude_recommendation = deps.build_exclude_recommendation_for_repo(
            analysis_repo_path=analysis_repo_path,
            manual_excludes=request.exclude_dirs,
            template_mode=request.exclude_template_mode,
            template_names=request.exclude_template_names,
            template_files=request.exclude_template_files,
        )
        exclude_summary = deps.build_exclude_summary(
            repository_name=repository_name,
            recommendation=exclude_recommendation,
        )
        final_exclude_dirs = exclude_recommendation.paths or None
        manual_warning_dirs = exclude_recommendation.manual_paths
        if (
            request.show_progress
            and console is not None
            and final_exclude_dirs is not None
        ):
            console.print_h1(
                "## " + tr("run.section.excluded_directories", paths=final_exclude_dirs)
            )

        analyzer = cast(
            GitRepoLOCAnalyzer,
            deps.create_analyzer(
                analysis_repo_path=analysis_repo_path,
                repo_ref=request.repo_path,
                branch_name=request.branch_name,
                cache_dir=request.output_dir / ".cache",
                output_dir=request.output_dir,
                since=request.since,
                until=request.until,
                authors=request.authors,
                languages=request.languages,
                exclude_dirs=final_exclude_dirs,
                exclude_warning_dirs=manual_warning_dirs,
                show_progress=request.show_progress,
            ),
        )

        deps.maybe_clear_cache(
            analyzer=analyzer,
            console=console,
            clear_cache=request.clear_cache,
            show_progress=request.show_progress,
        )

        def progress_callback(kind: str, value: int) -> None:
            event_kind = REPO_EVENT_ADVANCE
            if kind == "total":
                event_kind = REPO_EVENT_TOTAL
            elif kind == "scan_total":
                event_kind = REPO_EVENT_SCAN_TOTAL
            elif kind == "scan_advance":
                event_kind = REPO_EVENT_SCAN_ADVANCE
            emit_repo_progress(
                request.progress_queue,
                event_kind,
                request.index,
                repository_name,
                value,
            )

        loc_data = analyzer.get_commit_analysis(
            progress_callback=(
                progress_callback if request.progress_queue is not None else None
            )
        )
        analyzer.save_cache()

        repo_output_dir = deps.ensure_repo_output_dir(
            request.output_dir,
            repository_name,
        )
        loc_data.to_csv(repo_output_dir / "loc_data.csv")

        return (
            request.index,
            repository_name,
            loc_data,
            analyzer.get_warnings(),
            exclude_summary,
        )
    finally:
        emit_repo_progress(
            request.progress_queue,
            REPO_EVENT_FINISH,
            request.index,
            repository_name,
        )


def _analyze_repositories_sequential(
    *,
    args: argparse.Namespace,
    repo_entries: list[tuple],
    progress: tqdm,
    progress_queue: ProgressQueue | None = None,
    results: dict[int, pd.DataFrame],
    warnings: list[str],
    exclude_summaries: list[dict[str, object]],
    analyze_single_repository: Callable[
        ..., tuple[int, str, pd.DataFrame, list[str], dict[str, object]]
    ] = _analyze_single_repository,
    error_handler: Callable[[Exception], None] | None = None,
) -> None:
    """Analyze repositories sequentially and update results in-place."""
    for index, repo_entry in enumerate(repo_entries):
        (
            repo_path,
            branch_name,
            exclude_dirs,
            include_subpath,
            repo_template_mode,
            repo_template_names,
        ) = _unpack_repo_entry(repo_entry)
        resolved_excludes = _resolve_exclude_dirs(args, exclude_dirs)
        template_mode = _resolve_exclude_template_mode(args, repo_template_mode)
        template_names = _resolve_exclude_template_names(args, repo_template_names)
        request = _SingleRepositoryAnalysisRequest(
            index=index,
            repo_path=repo_path,
            branch_name=branch_name,
            exclude_dirs=resolved_excludes,
            include_subpath=include_subpath,
            exclude_template_mode=template_mode,
            exclude_template_names=template_names,
            exclude_template_files=getattr(args, "exclude_template_files", None),
            output_dir=args.output,
            since=args.since,
            until=args.until,
            authors=args.author_name,
            languages=args.lang,
            clear_cache=args.clear_cache,
            show_progress=False,
            update_remote_cache=getattr(args, "cache_policy", None) != "use",
            progress_queue=progress_queue,
        )
        try:
            (
                _,
                repository_name,
                loc_data,
                repo_warnings,
                exclude_summary,
            ) = analyze_single_repository(request)
        except (OSError, ValueError) as ex:
            if error_handler is None:
                raise
            error_handler(ex)
            continue
        warnings.extend(f"{repository_name}: {warning}" for warning in repo_warnings)
        exclude_summaries.append(exclude_summary)
        results[index] = loc_data
        progress.update(1)


def _build_repo_progress_bars(
    repo_entries: list[tuple],
    *,
    progress: tqdm,
    label_width: int,
    progress_factory: Callable[..., tqdm] = tqdm,
    bar_format: str = REPO_PROGRESS_BAR_FORMAT,
) -> tuple[dict[int, tqdm], dict[int, str]]:
    """Build child progress bars and labels for repository analysis."""
    repo_bars: dict[int, tqdm] = {}
    repo_labels: dict[int, str] = {}
    for index, repo_entry in enumerate(repo_entries):
        repo_path, _, _, _, _, _ = _unpack_repo_entry(repo_entry)
        repo_name = GitRepoLOCAnalyzer.get_repository_name(repo_path)
        label = truncate_repo_label(repo_name, label_width)
        repo_labels[index] = label
        repo_bars[index] = progress_factory(
            total=None,
            desc=format_repo_progress_description(
                label,
                tr("progress.repo.status.queued"),
            ),
            position=progress.pos + 1 + index,
            leave=True,
            unit="commit",
            bar_format=bar_format,
        )
    return repo_bars, repo_labels


def _cleanup_repo_progress_listener(
    *,
    stop_event: Event,
    listener_thread: Thread,
    repo_bars: dict[int, tqdm],
    manager: SyncManager,
    progress_queue: ProgressQueue,
) -> None:
    """Stop the progress listener and clean up related resources."""
    stop_event.set()
    try:
        progress_queue.put((REPO_EVENT_STOP, -1, "", 0))
    except AttributeError, EOFError, OSError, ValueError:
        pass
    listener_thread.join()
    for progress_bar in repo_bars.values():
        progress_bar.close()
    manager.shutdown()


def _analyze_repositories_parallel(
    *,
    args: argparse.Namespace,
    repo_entries: list[tuple],
    worker_count: int,
    progress: tqdm,
    progress_queue: ProgressQueue | None = None,
    results: dict[int, pd.DataFrame],
    warnings: list[str],
    exclude_summaries: list[dict[str, object]],
    analyze_single_repository: Callable[
        ..., tuple[int, str, pd.DataFrame, list[str], dict[str, object]]
    ] = _analyze_single_repository,
    error_handler: Callable[[Exception], None] | None = None,
) -> None:
    """Analyze repositories in parallel and update results in-place."""
    futures = []
    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        for index, repo_entry in enumerate(repo_entries):
            (
                repo_path,
                branch_name,
                exclude_dirs,
                include_subpath,
                repo_template_mode,
                repo_template_names,
            ) = _unpack_repo_entry(repo_entry)
            resolved_excludes = _resolve_exclude_dirs(args, exclude_dirs)
            template_mode = _resolve_exclude_template_mode(args, repo_template_mode)
            template_names = _resolve_exclude_template_names(args, repo_template_names)
            request = _SingleRepositoryAnalysisRequest(
                index=index,
                repo_path=repo_path,
                branch_name=branch_name,
                exclude_dirs=resolved_excludes,
                include_subpath=include_subpath,
                exclude_template_mode=template_mode,
                exclude_template_names=template_names,
                exclude_template_files=getattr(args, "exclude_template_files", None),
                output_dir=args.output,
                since=args.since,
                until=args.until,
                authors=args.author_name,
                languages=args.lang,
                clear_cache=args.clear_cache,
                show_progress=False,
                update_remote_cache=getattr(args, "cache_policy", None) != "use",
                progress_queue=progress_queue,
            )
            futures.append(
                executor.submit(
                    analyze_single_repository,
                    request,
                )
            )
        for future in as_completed(futures):
            try:
                (
                    index,
                    repository_name,
                    loc_data,
                    repo_warnings,
                    exclude_summary,
                ) = future.result()
            except (OSError, ValueError) as ex:
                if error_handler is None:
                    raise
                error_handler(ex)
                continue
            results[index] = loc_data
            warnings.extend(
                f"{repository_name}: {warning}" for warning in repo_warnings
            )
            exclude_summaries.append(exclude_summary)
            progress.update(1)


def _print_repository_warnings(warnings: list[str]) -> None:
    """Print collected repository warnings after progress bars have completed."""
    visible_warnings = [
        warning
        for warning in warnings
        if "excluded path does not exist:" not in warning
    ]
    if not visible_warnings:
        return
    print(tr("warnings.title"), file=sys.stderr)
    for warning in visible_warnings:
        print(f"- {warning}", file=sys.stderr)


def _print_repository_exclude_summaries(
    exclude_summaries: list[dict[str, object]],
) -> None:
    """Print collected repository exclude template decisions after progress bars."""
    visible_summaries = [
        summary for summary in exclude_summaries if summary.get("repository")
    ]
    if not visible_summaries:
        return
    print(tr("exclude.summary.title"))
    for summary in sorted(
        visible_summaries,
        key=lambda item: str(item.get("repository", "")).casefold(),
    ):
        repository = str(summary.get("repository", ""))
        label = truncate_repo_label(repository, REPO_PROGRESS_LABEL_WIDTH)
        raw_templates = (
            summary.get("templates")
            or summary.get("selected_template_names")
            or [tr("exclude.summary.none")]
        )
        if isinstance(raw_templates, list):
            templates = raw_templates
        else:
            templates = [str(raw_templates)]
        template_text = ", ".join(str(item) for item in templates)
        print(f"- {label:<{REPO_PROGRESS_LABEL_WIDTH}}: {template_text}")


def _resolve_worker_count(workers: int | None, repo_count: int) -> int:
    """Resolve repository worker count based on CPU availability and repo count."""
    if repo_count <= 1:
        return 1
    cpu_count = os.cpu_count() or 1
    if workers is None:
        resolved = min(cpu_count, repo_count)
    else:
        resolved = min(workers, repo_count)
    return max(1, resolved)


def analyze_git_repositories(
    args: argparse.Namespace,
    *,
    error_handler: Callable[[Exception], None] | None = None,
    worker_count_resolver: Callable[[int | None, int], int] = _resolve_worker_count,
    build_repo_progress_bars: (
        Callable[..., tuple[dict[int, tqdm], dict[int, str]]] | None
    ) = None,
    progress_listener_starter: Callable[
        ..., tuple[Event, Thread]
    ] = start_repo_progress_listener,
    sequential_analyzer: Callable[..., None] = _analyze_repositories_sequential,
    parallel_analyzer: Callable[..., None] = _analyze_repositories_parallel,
    progress_listener_cleanup: Callable[..., None] = _cleanup_repo_progress_listener,
    repository_warning_printer: Callable[
        [list[str]], None
    ] = _print_repository_warnings,
    repository_exclude_summary_printer: Callable[
        [list[dict[str, object]]], None
    ] = _print_repository_exclude_summaries,
    progress_factory: Callable[..., tqdm] = tqdm,
    manager_factory: Callable[[], SyncManager] = Manager,
) -> list[pd.DataFrame]:
    """Analyze the LOC in the configured Git repositories."""
    loc_data_repositories: list[pd.DataFrame] = []
    repo_entries = list(args.repo_paths)
    repo_count = len(repo_entries)
    worker_count = worker_count_resolver(args.workers, repo_count)
    results: dict[int, pd.DataFrame] = {}
    warnings: list[str] = []
    exclude_summaries: list[dict[str, object]] = []
    progress_bar_builder = build_repo_progress_bars or _build_repo_progress_bars

    with progress_factory(
        total=repo_count, desc=tr("progress.repo.analyzing")
    ) as progress:
        manager: SyncManager | None = None
        progress_queue: ProgressQueue | None = None
        repo_bars: dict[int, tqdm] = {}
        stop_event: Event | None = None
        listener_thread: Thread | None = None
        try:
            if repo_count:
                manager = manager_factory()
                progress_queue = manager.Queue()
                repo_bars, repo_labels = progress_bar_builder(
                    repo_entries,
                    progress=progress,
                    label_width=REPO_PROGRESS_LABEL_WIDTH,
                )
                stop_event, listener_thread = progress_listener_starter(
                    progress_queue=progress_queue,
                    repo_bars=repo_bars,
                    repo_labels=repo_labels,
                )
            if worker_count <= 1:
                sequential_analyzer(
                    args=args,
                    repo_entries=repo_entries,
                    progress=progress,
                    progress_queue=progress_queue,
                    results=results,
                    warnings=warnings,
                    exclude_summaries=exclude_summaries,
                    error_handler=error_handler,
                )
            else:
                parallel_analyzer(
                    args=args,
                    repo_entries=repo_entries,
                    worker_count=worker_count,
                    progress=progress,
                    progress_queue=progress_queue,
                    results=results,
                    warnings=warnings,
                    exclude_summaries=exclude_summaries,
                    error_handler=error_handler,
                )
        finally:
            if (
                manager is not None
                and progress_queue is not None
                and stop_event is not None
                and listener_thread is not None
            ):
                progress_listener_cleanup(
                    stop_event=stop_event,
                    listener_thread=listener_thread,
                    repo_bars=repo_bars,
                    manager=manager,
                    progress_queue=progress_queue,
                )

    args.exclude_metadata = exclude_summaries
    repository_exclude_summary_printer(exclude_summaries)
    repository_warning_printer(warnings)

    for index in sorted(results.keys()):
        loc_data_repositories.append(results[index])

    return loc_data_repositories
