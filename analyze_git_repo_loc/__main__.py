"""
Analyze Git repositories and visualize code LOC.

Author:    Nob Shinjo
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from colorama import Cursor, Fore, Style
from tqdm import tqdm

from analyze_git_repo_loc.chart_builder import ChartBuilder
from analyze_git_repo_loc.colored_console_printer import ColoredConsolePrinter
from analyze_git_repo_loc.utils import (
    analyze_git_repositories,
    analyze_trends,
    get_time_interval_and_period,
    handle_exception,
    parse_arguments,
    save_repository_branch_info,
)


def main() -> None:
    """
    main function to execute the program.
    """
    # Parsing command line arguments
    parser = argparse.ArgumentParser(
        prog="analyze_git_repo_loc",
        description="Analyze Git repositories and visualize code LOC.",
    )
    args = parse_arguments(parser)

    # Initialize ColoredConsolePrinter
    console = ColoredConsolePrinter()

    # Output program name and description.
    console.print_h1(f"# Start {parser.prog}.")
    print(Style.DIM + f"- {parser.description}", end=os.linesep + os.linesep)

    # Analyze the LOC in the Git repositories
    loc_data_repositories = analyze_git_repositories(args)
    time_interval, time_period = get_time_interval_and_period(args.interval)

    # Dataframe declaration
    language_analysis = pd.DataFrame()
    author_analysis = pd.DataFrame()
    repository_analysis = pd.DataFrame()

    # Convert analyzed data for visualization
    console.print_h1("\n# Forming dataframe type data.")
    for loc_data in tqdm(loc_data_repositories, desc="Processing loc data"):
        if "Datetime" not in loc_data.columns:
            console.print_colored(
                "Error: 'Datetime' column is not found in the dataframe.", Fore.RED
            )
            sys.exit(1)
        loc_data[time_interval] = (
            loc_data["Datetime"]
            .dt.tz_localize(None)
            .dt.to_period(time_period)
            .dt.to_timestamp()
        )
        # Create output directory for the repository
        if "Repository" not in loc_data.columns:
            console.print_colored(
                "Error: 'Repository' column is not found in the dataframe.", Fore.RED
            )
            sys.exit(1)
        repository_name = next(iter(loc_data["Repository"].unique()), "Unknown")
        repo_output_dir: Path = Path(args.output) / repository_name
        try:
            repo_output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as ex:
            handle_exception(ex)

        # 1. Stacked area trend chart of code volume by programming language per repository,
        #    bar graph of added/deleted code volume, and line graph of average code volume
        language_analysis = analyze_trends(
            category_column="Language",
            interval=time_interval,
            loc_data=loc_data,
            analysis_data=language_analysis,
            output_path=repo_output_dir,
        )

        # 2. Stacked area trend chart by author per repository
        author_analysis = analyze_trends(
            category_column="Author",
            interval=time_interval,
            loc_data=loc_data,
            analysis_data=author_analysis,
            output_path=repo_output_dir,
        )

        # 3. Stacked trend chart of code volume per repository,
        #    bar graph of added/deleted code volume, and line graph of average code volume
        repository_analysis = analyze_trends(
            category_column="Repository",
            interval=time_interval,
            loc_data=loc_data,
            analysis_data=repository_analysis,
        )

    # Save the analyzed data
    console.print_h1("\n# Save the analyzed data.")
    output_dir = Path(args.output) / datetime.now().strftime("%Y%m%d%H%M%S")
    save_analysis_data(
        language_analysis=language_analysis,
        author_analysis=author_analysis,
        repository_analysis=repository_analysis,
        output_dir=output_dir,
    )
    # Save the list of repositories and branch name
    save_repository_branch_info(args.repo_paths, output_dir / "repo_list.txt")

    # Generate charts
    console.print_h1("\n# Generate charts.")
    with tqdm(total=3, desc="Generating charts") as progress_bar:
        # 1. Stacked area trend chart of code volume by programming language per repository,
        generate_trend_chart(
            data=language_analysis,
            category_column="Language",
            time_interval=time_interval,
            output_path=Path(args.output),
        )
        progress_bar.update(1)

        # 2. Stacked area trend chart by author per repository
        generate_trend_chart(
            data=author_analysis,
            category_column="Author",
            time_interval=time_interval,
            output_path=Path(args.output),
        )
        progress_bar.update(1)

        # 3. Stacked trend chart of code volume per repository

        # Repository trend data
        repository_trend_data = prepare_trend_data(
            data=repository_analysis,
            time_interval=time_interval,
            category_column="Repository",
        )
        # Summary data
        summary_data = prepare_summary_data(
            data=repository_analysis, time_interval=time_interval
        )

        # Build the chart
        chart_builder: ChartBuilder = ChartBuilder()
        repository_trend_chart = chart_builder.build(
            trend_data=repository_trend_data,
            summary_data=summary_data,
            interval=time_interval,
            sub_title="All repositories",
        )

        # Show the chart
        repository_trend_chart.show()

        # Save the data and chart
        save_chart_data(
            trend_data=repository_trend_data,
            summary_data=summary_data,
            trend_chart=repository_trend_chart,
            output_prefix="Repository".lower(),
            output_path=output_dir,
        )
        progress_bar.update(1)
        progress_bar.close()

    console.print_h1("\n# LOC Analyze")
    print(Cursor.UP() + Cursor.FORWARD(50) + Fore.GREEN + "FINISH")


def save_analysis_data(
    language_analysis: pd.DataFrame,
    author_analysis: pd.DataFrame,
    repository_analysis: pd.DataFrame,
    output_dir: Path,
) -> None:
    """
    Save the analyzed data.

    Args:
        language_analysis (pd.DataFrame): The language analysis data.
        author_analysis (pd.DataFrame): The author analysis data.
        repository_analysis (pd.DataFrame): The repository analysis data.
        output_dir (Path): The output directory to save the data.
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as ex:
        handle_exception(ex)

    with tqdm(total=3, desc="Saving analyzed data") as progress_bar:
        language_analysis.to_csv(output_dir / "language_analysis.csv", index=False)
        progress_bar.update(1)

        author_analysis.to_csv(output_dir / "author_analysis.csv", index=False)
        progress_bar.update(1)

        repository_analysis.to_csv(output_dir / "repository_analysis.csv", index=False)
        progress_bar.update(1)


def prepare_trend_data(
    data: pd.DataFrame, time_interval: str, category_column: str
) -> pd.DataFrame:
    """
    Prepare trend data for the trend chart.

    Args:
        data (pd.DataFrame): The data to prepare the trend.
        time_interval (str): The interval to group by.
        category_column (str): The column name to group by.

    Returns:
        pd.DataFrame: The trend data for the trend chart.
    """
    trend_data = (
        data.pivot_table(
            index=time_interval, columns=category_column, values="SUM", aggfunc="sum"
        )
        .reset_index()
        .ffill()
    )
    # Sort the columns by the last value
    sorted_columns = trend_data.columns[1:][trend_data.iloc[-1, 1:].argsort()[::-1]]
    trend_data = trend_data.loc[:, [time_interval] + sorted_columns.tolist()]

    return trend_data


def prepare_summary_data(data: pd.DataFrame, time_interval: str) -> pd.DataFrame:
    """
    Prepare summary data for the trend chart.

    Args:
        data (pd.DataFrame): The data to prepare the summary.
        time_interval (str): The interval to group by.

    Returns:
        pd.DataFrame: The summary data for the trend chart.
    """
    summary_data = (
        data.groupby(time_interval)
        .agg(
            {
                "NLOC_Added": "sum",
                "NLOC_Deleted": "sum",
                "NLOC": "sum",
            }
        )
        .rename(columns={"NLOC_Added": "Added", "NLOC_Deleted": "Deleted"})
        .reset_index()[[time_interval, "Added", "Deleted", "NLOC"]]
    )
    summary_data["SUM"] = summary_data["NLOC"].cumsum()
    summary_data["Diff"] = summary_data["SUM"].diff()
    summary_data["Mean"] = summary_data["Diff"].mean()
    return summary_data


def generate_trend_chart(
    data: pd.DataFrame,
    category_column: str,
    time_interval: str,
    output_path: Path,
    sub_title: str = "",
) -> None:
    """
    Generate trend chart for each repository.

    Args:
        data (pd.DataFrame): The data to generate the trend chart.
        category_column (str): The column name to group by.
        time_interval (str): The time interval to group by.
        output_path (Path): The output path to save the chart.
        sub_title (str): The sub title for the chart.
    """

    if not data.empty:
        # Generate trend chart for each repository
        for repository in tqdm(
            data["Repository"].unique(), desc="Generating trend chart", leave=False
        ):
            loc_data = data[data["Repository"] == repository]
            branch_name = next(iter(loc_data["Branch"].unique()), "Unknown")

            # Language trend data
            trend_data = prepare_trend_data(
                data=loc_data,
                time_interval=time_interval,
                category_column=category_column,
            )

            # Summary data
            summary_data = prepare_summary_data(
                data=loc_data, time_interval=time_interval
            )

            # Build the chart
            chart_builder: ChartBuilder = ChartBuilder()
            trend_chart = chart_builder.build(
                trend_data=trend_data,
                summary_data=summary_data,
                interval=time_interval,
                sub_title=(
                    f"{repository} ({branch_name})" if sub_title == "" else sub_title
                ),
            )
            # Show the chart
            trend_chart.show()

            # Save the data and chart
            save_chart_data(
                trend_data=trend_data,
                summary_data=summary_data,
                trend_chart=trend_chart,
                output_prefix=category_column.lower(),
                output_path=output_path / repository,
            )


def save_chart_data(
    trend_data: pd.DataFrame,
    summary_data: pd.DataFrame,
    trend_chart: go.Figure,
    output_prefix: str,
    output_path: Path,
):
    """
    Save the trend data and chart.

    Args:
        trend_data (pd.DataFrame): The trend data to save.
        summary_data (pd.DataFrame): The summary data to save.
        trend_chart (go.Figure): The trend chart to save.
        output_prefix (str): The output prefix for the files.
        output_path (Path): The output path to save the files.

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
        trend_data.to_csv(
            output_path / f"{output_prefix}_trend_data.csv",
            index=False,
        )
        summary_data.to_csv(
            output_path / f"{output_prefix}_trend_summary.csv",
            index=False,
        )
        trend_chart.write_html(output_path / f"{output_prefix}_trend_chart.html")
    except (OSError, IOError, pd.errors.EmptyDataError) as ex:
        handle_exception(ex)


if __name__ == "__main__":
    main()
