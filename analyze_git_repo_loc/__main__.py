"""
Analyzing Git Repositories and Visualizing Code LOC.

This script analyzes the lines of code (LOC) in Git repositories 
and visualizes the data through various charts. 
It processes the LOC data, categorizes it by programming language, author,
 and repository, and generates trend charts to show the evolution of code volume over time.

Functions:
    main() -> None:
        Main function to execute the program. It parses command line arguments, 
        initializes the console printer, 
        analyzes the LOC data, forms dataframes, saves the analyzed data, and generates charts.
    save_analysis_data(language_analysis: pd.DataFrame, author_analysis: pd.DataFrame, 
    repository_analysis: pd.DataFrame, output_dir: Path) -> None:
        Saves the analyzed data to CSV files in the specified output directory.
    prepare_trend_data(data: pd.DataFrame, time_interval: str, category_column: str)
      -> pd.DataFrame:
        Prepares trend data for the trend chart by pivoting the data and sorting the columns.
    prepare_summary_data(data: pd.DataFrame, time_interval: str) -> pd.DataFrame:
        Prepares summary data for the trend chart by aggregating the data and calculating 
        cumulative sums and differences.
    generate_trend_chart(data: pd.DataFrame, category_column: str, time_interval: str,
        output_path: Path, sub_title: str = "") -> None:
        Generates trend charts for each repository and saves the data and charts 
        to the specified output path.
    save_chart_data(trend_data: pd.DataFrame, summary_data: pd.DataFrame, trend_chart: go.Figure,
         output_prefix: str, output_path: Path):
        Saves the trend data and chart to CSV and HTML files in the specified output path.
    generate_repository_trend_chart(data: pd.DataFrame, time_interval: str, output_path: Path) -> None:
        Generates a trend chart for all repositories and saves the data and chart 
        to the specified output path.
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

from analyze_git_repo_loc.chart_builder import ChartBuilder, ChartStrategy
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
    repository_trend_analysis = pd.DataFrame()

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
        repository_trend_analysis = analyze_trends(
            category_column="Repository",
            interval=time_interval,
            loc_data=loc_data,
            analysis_data=repository_trend_analysis,
        )

    # Save the analyzed data
    console.print_h1("\n# Save the analyzed data.")
    output_dir = Path(args.output) / datetime.now().strftime("%Y%m%d%H%M%S")
    data_list = {
        "language_analysis": language_analysis,
        "author_analysis": author_analysis,
        "repository_trend_analysis": repository_trend_analysis,
    }
    save_analysis_data(data_list=data_list, output_dir=output_dir)
    # Save the list of repositories and branch name
    save_repository_branch_info(args.repo_paths, output_dir / "repo_list.txt")

    # Generate charts
    console.print_h1("\n# Generate charts.")
    with tqdm(total=4, desc="Generating charts") as progress_bar:
        # 1. Stacked area trend chart of code volume by programming language per repository,
        generate_trend_chart(
            data=language_analysis,
            category_column="Language",
            time_interval=time_interval,
            output_path=Path(args.output),
            no_plot_show=args.no_plot_show,
        )
        progress_bar.update(1)

        # 2. Stacked area trend chart by author per repository
        generate_trend_chart(
            data=author_analysis,
            category_column="Author",
            time_interval=time_interval,
            output_path=Path(args.output),
            no_plot_show=args.no_plot_show,
        )
        progress_bar.update(1)

        # 3. Stacked trend chart of code volume per repository
        generate_all_repositories_trend_chart(
            data=repository_trend_analysis,
            time_interval=time_interval,
            category_column="Repository",
            output_path=output_dir,
            no_plot_show=args.no_plot_show,
        )
        progress_bar.update(1)

        # 4. Stacked bar chart of author contribution per repository
        generate_author_contribution_chart(
            data=author_analysis,
            output_path=output_dir,
            no_plot_show=args.no_plot_show,
        )
        progress_bar.update(1)

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
    sorted_columns = (
        trend_data.iloc[-1, 1:]
        .infer_objects(copy=False)
        .sort_values(ascending=False)
        .index.tolist()
    )
    trend_data = trend_data.loc[:, [time_interval] + sorted_columns]

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


def prepare_author_contribution_data(data: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare author contribution data for the bar chart.

    Args:
        data (pd.DataFrame): The data to prepare the author contribution.

    Returns:
        pd.DataFrame: The author contribution data for the trend chart.
    """
    contribution_data = (
        data.groupby(["Author", "Repository"])
        .agg(
            {
                "NLOC": "sum",
            }
        )
        .reset_index()[["Author", "Repository", "NLOC"]]
    )
    summary_data = contribution_data.pivot_table(
        index="Author", columns="Repository", values="NLOC", aggfunc="sum"
    ).reset_index()
    # Sort the columns by the last value
    sorted_columns = (
        summary_data.iloc[-1, 1:]
        .infer_objects(copy=False)
        .sort_values(ascending=False)
        .index.tolist()
    )
    summary_data = summary_data.loc[:, ["Author"] + sorted_columns]
    # Sort the rows by the sum of values
    sorted_indices = summary_data.iloc[:, 1:].sum(axis=1).argsort()[::-1]
    summary_data = summary_data.iloc[sorted_indices].reset_index(drop=True)
    return summary_data


def generate_trend_chart(
    data: pd.DataFrame,
    category_column: str,
    time_interval: str,
    output_path: Path,
    sub_title: str = "",
    no_plot_show: bool = False,
) -> None:
    """
    Generate trend chart for each repository.

    Args:
        data (pd.DataFrame): The data to generate the trend chart.
        category_column (str): The column name to group by.
        time_interval (str): The time interval to group by.
        output_path (Path): The output path to save the chart.
        sub_title (str): The sub title for the chart.
        no_plot_show (bool): If True, the chart will not be shown.
    """
    if data.empty:
        return

    # Generate trend chart for each repository
    for repository in tqdm(
        data["Repository"].unique(), desc="Generating trend chart", leave=False
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
        chart_builder: ChartBuilder = ChartBuilder()
        chart_builder.set_strategy(ChartStrategy.TREND)
        try:
            trend_chart = chart_builder.build(
                trend_data=trend_data,
                summary_data=summary_data,
                interval=time_interval,
                sub_title=(
                    f"by {category_column} - {repository} ({branch_name})"
                    if sub_title == ""
                    else f"by {category_column} - {sub_title}"
                ),
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
    if len(data["Repository"].unique()) == 1:
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
    try:
        chart_builder.set_strategy(ChartStrategy.TREND)
        trend_chart = chart_builder.build(
            trend_data=trend_data,
            summary_data=summary_data,
            interval=time_interval,
            sub_title=f"by {category_column} - All repositories",
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
    if len(data["Repository"].unique()) == 1:
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
            sub_title="by Author - All repositories",
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
