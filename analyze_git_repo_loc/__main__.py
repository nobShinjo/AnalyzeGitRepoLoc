"""
Analyze Git repositories and generate LOC charts and reports.

Description:
    Runs the CLI workflow: parse arguments, analyze repositories, save CSVs, and
    generate charts and reports for each run.
    Handles argument parsing, data aggregation, and output layout.
Functions:
    main: Run the CLI workflow for analysis and reporting.
            Coordinates parsing, analysis, charting, and report outputs.
    save_analysis_data: Persist analysis CSV outputs for the run.
            Writes aggregated analysis dataframes to CSV files.
    generate_trend_chart: Create per-repository trend charts.
            Builds and saves language/author trend charts per repository.
    save_chart_data: Write chart data and HTML outputs to disk.
            Serializes trend data, summaries, and Plotly HTML outputs.
    generate_all_repositories_trend_chart: Create aggregate trend charts.
            Builds combined charts across all repositories.
    generate_author_contribution_chart: Create author contribution charts.
            Builds stacked contribution charts by repository.
"""

import argparse
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from colorama import Cursor, Fore, Style
from tqdm import tqdm

from analyze_git_repo_loc.analysis_helpers import (
    prepare_author_contribution_data,
    prepare_summary_data,
    prepare_trend_data,
)
from analyze_git_repo_loc.chart_builder import ChartBuilder, ChartStrategy
from analyze_git_repo_loc.colored_console_printer import ColoredConsolePrinter
from analyze_git_repo_loc.html_report import ProgressEvent, generate_html_report
from analyze_git_repo_loc.init_wizard import run_init_config_wizard
from analyze_git_repo_loc.markdown_summary import generate_markdown_summary
from analyze_git_repo_loc.remote_catalog import (
    RemoteCatalogError,
)
from analyze_git_repo_loc.tui_selector import TuiSelectionCancelled
from analyze_git_repo_loc.tui_wizard import run_tui_wizard
from analyze_git_repo_loc.utils import (
    analyze_git_repositories,
    analyze_trends,
    get_time_interval_and_period,
    handle_exception,
    parse_arguments,
    save_repository_branch_info,
)
from analyze_git_repo_loc.yaml_config import load_yaml_data


class _ReportProgressTracker:
    """
    Track parent/child progress bars for HTML report generation.
    """

    def __init__(self, progress_bar: tqdm) -> None:
        self._progress_bar = progress_bar
        self._child_bar: tqdm | None = None
        self._child_label: str | None = None

    def __call__(self, event: ProgressEvent) -> None:
        if event.kind == "parent":
            self._handle_parent(event)
        else:
            self._handle_child(event)

    def _handle_parent(self, event: ProgressEvent) -> None:
        if self._child_bar is not None:
            self._child_bar.close()
            self._child_bar = None
            self._child_label = None
        if event.total is not None:
            self._progress_bar.total = event.total
            self._progress_bar.refresh()
        if event.label:
            self._progress_bar.set_description_str(event.label)
        if event.advance:
            self._progress_bar.update(event.advance)

    def _handle_child(self, event: ProgressEvent) -> None:
        if (
            self._child_bar is None
            or event.total is not None
            or event.label != self._child_label
        ):
            if self._child_bar is not None:
                self._child_bar.close()
            self._child_label = event.label
            self._child_bar = tqdm(
                total=event.total or 0,
                desc=event.label,
                leave=False,
                position=self._progress_bar.pos + 1,
            )
        if event.advance and self._child_bar is not None:
            self._child_bar.update(event.advance)
        if event.done and self._child_bar is not None:
            self._child_bar.close()
            self._child_bar = None
            self._child_label = None


def _print_start(console: ColoredConsolePrinter, parser: argparse.ArgumentParser) -> None:
    console.print_h1(f"# Start {parser.prog}.")
    print(Style.DIM + f"- {parser.description}", end=os.linesep + os.linesep)


def _apply_tui_repository_selection(args: argparse.Namespace) -> None:
    """
    Run TUI repository selection and update args.repo_paths.

    Args:
        args (argparse.Namespace): Parsed CLI arguments.
    """
    if not getattr(args, "tui", False):
        return
    try:
        config_data = load_yaml_data(args.config)
        run_tui_wizard(args, config_data)
    except (RemoteCatalogError, RuntimeError, TuiSelectionCancelled, ValueError) as ex:
        print(str(ex), file=sys.stderr)
        sys.exit(1)


def _prepare_loc_data(
    loc_data: pd.DataFrame,
    *,
    time_interval: str,
    time_period: str,
    console: ColoredConsolePrinter,
) -> str:
    if "Datetime" not in loc_data.columns:
        console.print_colored(
            "Error: 'Datetime' column is not found in the dataframe.",
            Fore.RED,
        )
        sys.exit(1)
    loc_data[time_interval] = (
        loc_data["Datetime"]
        .dt.tz_localize(None)
        .dt.to_period(time_period)
        .dt.to_timestamp()
    )
    if "Repository" not in loc_data.columns:
        console.print_colored(
            "Error: 'Repository' column is not found in the dataframe.",
            Fore.RED,
        )
        sys.exit(1)
    return next(iter(loc_data["Repository"].unique()), "Unknown")


def _ensure_repo_output_dir(output_root: Path, repository_name: str) -> Path:
    repo_output_dir = output_root / repository_name
    try:
        repo_output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as ex:
        handle_exception(ex)
    return repo_output_dir


def _build_analysis_data(
    *,
    loc_data_repositories: list[pd.DataFrame],
    time_interval: str,
    time_period: str,
    output_root: Path,
    console: ColoredConsolePrinter,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    language_analysis = pd.DataFrame()
    author_analysis = pd.DataFrame()
    repository_trend_analysis = pd.DataFrame()

    console.print_h1("\n# Forming dataframe type data.")
    for loc_data in tqdm(loc_data_repositories, desc="Processing loc data"):
        repository_name = _prepare_loc_data(
            loc_data,
            time_interval=time_interval,
            time_period=time_period,
            console=console,
        )
        repo_output_dir = _ensure_repo_output_dir(output_root, repository_name)
        language_analysis = analyze_trends(
            category_column="Language",
            interval=time_interval,
            loc_data=loc_data,
            analysis_data=language_analysis,
            output_path=repo_output_dir,
        )
        author_analysis = analyze_trends(
            category_column="Author",
            interval=time_interval,
            loc_data=loc_data,
            analysis_data=author_analysis,
            output_path=repo_output_dir,
        )
        repository_trend_analysis = analyze_trends(
            category_column="Repository",
            interval=time_interval,
            loc_data=loc_data,
            analysis_data=repository_trend_analysis,
        )
    return language_analysis, author_analysis, repository_trend_analysis


def _save_analysis_outputs(
    *,
    output_dir: Path,
    args: argparse.Namespace,
    time_interval: str,
    language_analysis: pd.DataFrame,
    author_analysis: pd.DataFrame,
    repository_trend_analysis: pd.DataFrame,
) -> None:
    data_list = {
        "language_analysis": language_analysis,
        "author_analysis": author_analysis,
        "repository_trend_analysis": repository_trend_analysis,
    }
    save_analysis_data(data_list=data_list, output_dir=output_dir)
    save_repository_branch_info(args.repo_paths, output_dir / "repo_list.txt")
    try:
        generate_markdown_summary(
            output_dir=output_dir,
            time_interval=time_interval,
            language_analysis=language_analysis,
            author_analysis=author_analysis,
            repository_trend_analysis=repository_trend_analysis,
        )
    except OSError as ex:
        handle_exception(ex)


def _generate_charts(
    *,
    output_root: Path,
    output_dir: Path,
    time_interval: str,
    suppress_plot_show: bool,
    language_analysis: pd.DataFrame,
    author_analysis: pd.DataFrame,
    repository_trend_analysis: pd.DataFrame,
) -> None:
    with tqdm(total=5, desc="Charts: Language trend") as progress_bar:
        generate_trend_chart(
            data=language_analysis,
            category_column="Language",
            time_interval=time_interval,
            output_path=output_root,
            no_plot_show=suppress_plot_show,
        )
        progress_bar.update(1)

        progress_bar.set_description_str("Charts: Author trend")
        generate_trend_chart(
            data=author_analysis,
            category_column="Author",
            time_interval=time_interval,
            output_path=output_root,
            no_plot_show=suppress_plot_show,
        )
        progress_bar.update(1)

        progress_bar.set_description_str("Charts: Repository trend")
        generate_all_repositories_trend_chart(
            data=repository_trend_analysis,
            time_interval=time_interval,
            category_column="Repository",
            output_path=output_dir,
            no_plot_show=suppress_plot_show,
        )
        progress_bar.update(1)

        progress_bar.set_description_str("Charts: Author contribution")
        generate_author_contribution_chart(
            data=author_analysis,
            output_path=output_dir,
            no_plot_show=suppress_plot_show,
        )
        progress_bar.update(1)

        progress_bar.set_description_str("Charts: Author aggregate")
        generate_all_repositories_trend_chart(
            data=repository_trend_analysis,
            time_interval=time_interval,
            category_column="Author",
            output_path=output_dir,
            no_plot_show=suppress_plot_show,
        )
        progress_bar.update(1)


def _generate_report(
    *,
    output_dir: Path,
    output_root: Path,
    time_interval: str,
    loc_data_repositories: list[pd.DataFrame],
    language_analysis: pd.DataFrame,
    author_analysis: pd.DataFrame,
    repository_trend_analysis: pd.DataFrame,
) -> None:
    with tqdm(desc="Generating HTML report") as progress_bar:
        report_progress = _ReportProgressTracker(progress_bar)
        try:
            generate_html_report(
                output_dir=output_dir,
                charts_root=output_root,
                time_interval=time_interval,
                language_analysis=language_analysis,
                author_analysis=author_analysis,
                repository_trend_analysis=repository_trend_analysis,
                detail_analysis=(
                    pd.concat(loc_data_repositories, ignore_index=True)
                    if loc_data_repositories
                    else pd.DataFrame()
                ),
                progress_callback=report_progress,
            )
        except OSError as ex:
            handle_exception(ex)


def _maybe_open_report(*, output_dir: Path, args: argparse.Namespace, repo_count: int) -> None:
    if repo_count > 1 and not args.no_plot_show:
        report_path = output_dir / "report.html"
        if report_path.exists():
            webbrowser.open(report_path.resolve().as_uri())


def _format_output_summary(
    output_dir: Path, output_root: Path | None = None
) -> list[str]:
    """
    Format the final artifact summary for a completed analysis run.

    Args:
        output_dir (Path): Timestamped output directory for the run.
        output_root (Path | None): Root output directory for charts and cache.

    Returns:
        list[str]: Human-readable artifact summary lines.
    """
    resolved_output_root = output_root or output_dir.parent
    return [
        "Finished",
        f"Report: {output_dir / 'report.html'}",
        f"Summary: {output_dir / 'summary.md'}",
        f"Data: {output_dir / '*.csv'}",
        f"Run data: {output_dir}",
        f"Repository charts: {resolved_output_root}",
        f"Cache: {resolved_output_root / '.cache'}",
    ]


def _print_output_summary(
    console: ColoredConsolePrinter, output_dir: Path, output_root: Path
) -> None:
    """
    Print generated artifact paths for a completed analysis run.

    Args:
        console (ColoredConsolePrinter): Console printer for colored output.
        output_dir (Path): Timestamped output directory for the run.
        output_root (Path): Root output directory for charts and cache.
    """
    lines = _format_output_summary(output_dir, output_root)
    console.print_colored(lines[0], color=Fore.GREEN, bright=True)
    for line in lines[1:]:
        label, _, value = line.partition(": ")
        console.print_colored(f"{label}: ", color=Fore.CYAN, bright=True, end="")
        print(value)


def main() -> None:
    """
    Main function to execute the program.
    """
    # Parsing command line arguments
    parser = argparse.ArgumentParser(
        prog="analyze_git_repo_loc",
        description="Analyze Git repositories and visualize code LOC.",
    )
    args = parse_arguments(parser)
    if args.command == "init":
        run_init_config_wizard(default_path=args.config)
        return

    # Initialize ColoredConsolePrinter
    console = ColoredConsolePrinter()
    _apply_tui_repository_selection(args)

    # Output program name and description.
    _print_start(console, parser)

    # Analyze the LOC in the Git repositories
    loc_data_repositories = analyze_git_repositories(args)
    time_interval, time_period = get_time_interval_and_period(args.interval)

    repo_count = len(loc_data_repositories)
    suppress_plot_show = args.no_plot_show or repo_count > 1
    output_root = Path(args.output)
    language_analysis, author_analysis, repository_trend_analysis = _build_analysis_data(
        loc_data_repositories=loc_data_repositories,
        time_interval=time_interval,
        time_period=time_period,
        output_root=output_root,
        console=console,
    )

    # Save the analyzed data
    console.print_h1("\n# Save the analyzed data.")
    output_dir = output_root / datetime.now().strftime("%Y%m%d%H%M%S")
    _save_analysis_outputs(
        output_dir=output_dir,
        args=args,
        time_interval=time_interval,
        language_analysis=language_analysis,
        author_analysis=author_analysis,
        repository_trend_analysis=repository_trend_analysis,
    )

    # Generate charts
    console.print_h1("\n# Generate charts.")
    _generate_charts(
        output_root=output_root,
        output_dir=output_dir,
        time_interval=time_interval,
        suppress_plot_show=suppress_plot_show,
        language_analysis=language_analysis,
        author_analysis=author_analysis,
        repository_trend_analysis=repository_trend_analysis,
    )

    console.print_h1("\n# Generate HTML report.")
    _generate_report(
        output_dir=output_dir,
        output_root=output_root,
        time_interval=time_interval,
        loc_data_repositories=loc_data_repositories,
        language_analysis=language_analysis,
        author_analysis=author_analysis,
        repository_trend_analysis=repository_trend_analysis,
    )

    _maybe_open_report(output_dir=output_dir, args=args, repo_count=repo_count)
    _print_output_summary(console, output_dir, output_root)

    console.print_h1("\n# LOC Analyze")
    print(Cursor.UP() + Cursor.FORWARD(50) + Fore.GREEN + "FINISH")


def save_analysis_data(
    data_list: dict[str, pd.DataFrame],
    output_dir: Path,
) -> None:
    """
    Save the analyzed data.

    Args:
        data_list (dict[str, pd.DataFrame]): The list of dataframes to save.
        output_dir (Path): The output directory to save the data.
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as ex:
        handle_exception(ex)

    # dictからname key, data valueを取り出して、name.csvとして保存
    for name, data in tqdm(data_list.items(), desc="Saving analyzed data"):
        data.to_csv(output_dir / f"{name}.csv", index=False)


def generate_trend_chart(
    data: pd.DataFrame,
    category_column: str,
    time_interval: str,
    output_path: Path,
    title: str = "",
    no_plot_show: bool = False,
) -> None:
    """
    Generate trend chart for each repository.

    Args:
        data (pd.DataFrame): The data to generate the trend chart.
        category_column (str): The column name to group by.
        time_interval (str): The time interval to group by.
        output_path (Path): The output path to save the chart.
        title (str): The title for the chart.
        no_plot_show (bool): If True, the chart will not be shown.
    """
    if data.empty:
        return

    chart_builder: ChartBuilder = ChartBuilder()
    chart_builder.set_strategy(ChartStrategy.TREND)

    # Generate trend chart for each repository
    unique_repositories = data["Repository"].unique()
    for repository in tqdm(
        unique_repositories, desc="Generating trend chart", leave=False
    ):
        loc_data = data[data["Repository"] == repository]
        branch_name = next(iter(loc_data["Branch"].unique()), "Unknown")

        # LOC trend data
        trend_data = prepare_trend_data(
            data=loc_data,
            time_interval=time_interval,
            category_column=category_column,
        )

        # Summary data
        summary_data = prepare_summary_data(data=loc_data, time_interval=time_interval)

        # Build the chart
        try:
            full_title = (
                f"NLOC trend by {category_column} - {repository} ({branch_name})"
                if title == ""
                else f"by {category_column} - {title}"
            )
            trend_chart = chart_builder.build(
                trend_data=trend_data,
                summary_data=summary_data,
                interval=time_interval,
                title=full_title,
            )
        except ValueError as ex:
            handle_exception(ex)
            continue

        # Show the chart
        if not no_plot_show:
            trend_chart.show()

        # Save the data and chart
        save_chart_data(
            output_prefix=category_column.lower(),
            output_path=output_path / repository,
            trend_data=trend_data,
            summary_data=summary_data,
            trend_chart=trend_chart,
        )


def save_chart_data(
    output_prefix: str,
    output_path: Path,
    trend_data: pd.DataFrame = None,
    summary_data: pd.DataFrame = None,
    trend_chart: go.Figure = None,
    contribution_chart: go.Figure = None,
):
    """
    Save the trend data and chart.

    Args:
        output_prefix (str): The output prefix for the files.
        output_path (Path): The output path to save the files.
        trend_data (pd.DataFrame): The trend data to save.
        summary_data (pd.DataFrame): The summary data to save.
        trend_chart (go.Figure): The trend chart to save.
        contribution_chart (go.Figure): The contribution chart to save.

    Raises:
        OSError: If an error occurs while saving the files.
        IOError: If an error occurs while saving the files.
        pd.errors.EmptyDataError: If the data is empty.
    """
    try:
        # Check if the output path is a Path object
        if not isinstance(output_path, Path):
            output_path = Path(output_path)
        # Create the output directory
        output_path.mkdir(parents=True, exist_ok=True)
        # Save the data and chart
        if trend_data is not None:
            trend_data.to_csv(
                output_path / f"{output_prefix}_trend_data.csv",
                index=False,
            )
        if summary_data is not None:
            summary_data.to_csv(
                output_path / f"{output_prefix}_summary_data.csv",
                index=False,
            )
        if trend_chart is not None:
            trend_chart.write_html(output_path / f"{output_prefix}_chart.html")
        if contribution_chart is not None:
            contribution_chart.write_html(
                output_path / f"{output_prefix}_contribution_chart.html"
            )

    except (OSError, IOError, pd.errors.EmptyDataError) as ex:
        handle_exception(ex)


def generate_all_repositories_trend_chart(
    data: pd.DataFrame,
    time_interval: str,
    category_column: str,
    output_path: Path,
    no_plot_show: bool = False,
) -> None:
    """
    Generate a trend chart for all repositories.

    Generate a trend chart for all repositories and save the data and chart
    to the specified output path. If the data is empty or there is only one
    repository, the function returns without generating the chart.

    Args:
        data (pd.DataFrame): The data to generate the trend chart.
        time_interval (str): The time interval to group by.
        category_column (str): The column name to group by.
        output_path (Path): The output path to save the chart.
        no_plot_show (bool): If True, the chart will not be shown.
    """
    # Check if the data is empty or there is only one repository
    if data.empty:
        return
    unique_repositories = data["Repository"].unique()
    if len(unique_repositories) == 1:
        return

    # Repository trend data
    trend_data = prepare_trend_data(
        data=data,
        time_interval=time_interval,
        category_column=category_column,
    )
    # Summary data
    summary_data = prepare_summary_data(data=data, time_interval=time_interval)

    # Build the chart
    chart_builder: ChartBuilder = ChartBuilder()
    chart_builder.set_strategy(ChartStrategy.TREND)
    try:
        trend_chart = chart_builder.build(
            trend_data=trend_data,
            summary_data=summary_data,
            interval=time_interval,
            title=f"NLOC trend by {category_column} - All repositories",
        )
    except ValueError as ex:
        handle_exception(ex)

    # Show the chart
    if not no_plot_show:
        trend_chart.show()

    # Save the data and chart
    save_chart_data(
        output_prefix=category_column.lower(),
        output_path=output_path,
        trend_data=trend_data,
        summary_data=summary_data,
        trend_chart=trend_chart,
    )


def generate_author_contribution_chart(
    data: pd.DataFrame,
    output_path: Path,
    no_plot_show: bool = False,
) -> None:
    """
    Generate author contribution chart.

    Generate a bar chart of author contribution per repository and save the data and chart
    to the specified output path. If the data is empty or there is only one repository,
    the function returns without generating the chart.

    Args:
        data (pd.DataFrame): The data to generate the author contribution chart.
        output_path (Path): The output path to save the chart.
        no_plot_show (bool): If True, the chart will not be shown.

    Raises:
        ValueError: If an error occurs while building the chart.
    """
    # Check if the data is empty or there is only one repository
    if data.empty:
        return
    unique_repositories = data["Repository"].unique()
    if len(unique_repositories) == 1:
        return

    # Author contribution data
    author_contribution_data = prepare_author_contribution_data(data)

    # Build the chart
    chart_builder: ChartBuilder = ChartBuilder()
    chart_builder.set_strategy(ChartStrategy.AUTHOR_CONTRIBUTION)
    try:
        author_contribution_chart = chart_builder.build(
            trend_data=None,
            summary_data=author_contribution_data,
            interval=None,
            title="Author contribution by repository - All repositories",
        )
    except ValueError as ex:
        handle_exception(ex)

    # Show the chart
    if not no_plot_show:
        author_contribution_chart.show()

    # Save the data and chart
    save_chart_data(
        output_prefix="author_contribution",
        output_path=output_path,
        summary_data=author_contribution_data,
        contribution_chart=author_contribution_chart,
    )


if __name__ == "__main__":
    main()
