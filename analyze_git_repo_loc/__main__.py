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

    # Convert analyzed data for visualization
    # 1. Stacked area trend chart of code volume by programming language per repository,
    #    bar graph of added/deleted code volume, and line graph of average code volume
    # 2. Stacked area trend chart by author per repository
    # 3. Stacked trend chart of code volume per repository, bar graph of added/deleted code volume,
    #    and line graph of average code volume
    # 4. Aggregate each data daily, weekly, and monthly
    console.print_h1("# Forming dataframe type data.")
    # Dataframe declaration
    language_analysis = pd.DataFrame()
    author_analysis = pd.DataFrame()
    repository_analysis = pd.DataFrame()
    time_interval, time_period = get_time_interval_and_period(args.interval)
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
        output_dir_for_repo: Path = Path(args.output) / repository_name
        try:
            output_dir_for_repo.mkdir(parents=True, exist_ok=True)
        except OSError as ex:
            handle_exception(ex)

        # 1. Stacked area trend chart of code volume by programming language per repository,
        #    bar graph of added/deleted code volume, and line graph of average code volume
        language_trends = analyze_trends(
            category_column="Language", interval=time_interval, loc_data=loc_data
        )
        language_trends.to_csv(output_dir_for_repo / "language_trends.csv", index=False)
        language_analysis = pd.concat(
            [language_analysis, language_trends], ignore_index=True
        )

        # 2. Stacked area trend chart by author per repository
        author_trends = analyze_trends(
            category_column="Author", interval=time_interval, loc_data=loc_data
        )
        author_trends.to_csv(output_dir_for_repo / "author_trends.csv", index=False)
        author_analysis = pd.concat([author_analysis, author_trends], ignore_index=True)

        # 3. Stacked trend chart of code volume per repository,
        #    bar graph of added/deleted code volume, and line graph of average code volume
        repository_trends = analyze_trends(
            category_column="Repository", interval=time_interval, loc_data=loc_data
        )
        repository_analysis = pd.concat(
            [repository_analysis, repository_trends], ignore_index=True
        )

    # Save the analyzed data
    console.print_h1("# Save the analyzed data.")
    current_date = datetime.now()
    output_dir = Path(args.output) / current_date.strftime("%Y%m%d%H%M%S")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as ex:
        handle_exception(ex)
    language_analysis.to_csv(output_dir / "language_analysis.csv", index=False)
    author_analysis.to_csv(output_dir / "author_analysis.csv", index=False)
    repository_analysis.to_csv(output_dir / "repository_analysis.csv", index=False)
    # Save the list of repositories and branch name
    save_repository_branch_info(args.repo_paths, output_dir / "repo_list.txt")

    # Generate charts
    console.print_h1("# Generate charts.")
    # 1. Stacked area trend chart of code volume by programming language per repository,
    #    bar graph of added/deleted code volume, and line graph of average code volume
    # 2. Stacked area trend chart by author per repository
    # 3. Stacked trend chart of code volume per repository,
    #    bar graph of added/deleted code volume, and line graph of average code volume
    # 4. Aggregate each data daily, weekly, and monthly

    # Initialize ChartBuilder
    chart_builder: ChartBuilder = ChartBuilder()
    # chart: go.Figure = None

    # 1. Stacked area trend chart of code volume by programming language per repository,
    if not language_analysis.empty:
        for repository in language_analysis["Repository"].unique():
            loc_data = language_analysis[language_analysis["Repository"] == repository]
            branch_name = next(iter(loc_data["Branch"].unique()), "Unknown")

            # Summary data
            summary_data = loc_data[
                [time_interval, "SUM", "NLOC_Added", "NLOC_Deleted", "Diff", "Mean"]
            ].rename(columns={"NLOC_Added": "Added", "NLOC_Deleted": "Deleted"})

            language_trend_data = (
                loc_data.pivot_table(
                    index=time_interval, columns="Language", values="SUM", aggfunc="sum"
                )
                .reset_index()
                .apply(pd.to_numeric, errors="coerce")
            )

            language_trend_chart = chart_builder.build(
                trend_data=language_trend_data,
                summary_data=summary_data,
                color_data="Language",
                interval=time_interval,
                sub_title=f"{repository} ({branch_name})",
            )
            chart_output_dir = Path(args.output) / repository
            language_trend_chart.write_html(
                chart_output_dir / "language_trend_chart.html"
            )

    # 2. Stacked area trend chart by author per repository
    if not author_analysis.empty:
        for repository in author_analysis["Repository"].unique():
            loc_data = author_analysis[author_analysis["Repository"] == repository]
            branch_name = next(iter(loc_data["Branch"].unique()), "Unknown")
            # Summary data
            summary_data = loc_data[
                [time_interval, "SUM", "NLOC_Added", "NLOC_Deleted", "Diff", "Mean"]
            ].rename(columns={"NLOC_Added": "Added", "NLOC_Deleted": "Deleted"})

            author_trend_data = (
                loc_data.pivot_table(
                    index=time_interval, columns="Author", values="SUM", aggfunc="sum"
                )
                .reset_index()
                .apply(pd.to_numeric, errors="coerce")
            )

            author_trend_chart = chart_builder.build(
                trend_data=author_trend_data,
                summary_data=summary_data,
                color_data="Author",
                interval=time_interval,
                sub_title=f"{repository} ({branch_name})",
            )
            chart_output_dir = Path(args.output) / repository
            author_trend_chart.write_html(chart_output_dir / "author_trend_chart.html")

    # 3. Stacked trend chart of code volume per repository,

    repository_trend_data = (
        repository_analysis.pivot_table(
            index=time_interval, columns="Repository", values="SUM", aggfunc="sum"
        )
        .reset_index()
        .apply(pd.to_numeric, errors="coerce")
    )
    summary_data = repository_analysis[
        [time_interval, "SUM", "NLOC_Added", "NLOC_Deleted", "Diff", "Mean"]
    ].rename(columns={"NLOC_Added": "Added", "NLOC_Deleted": "Deleted"})

    repository_trend_chart = chart_builder.build(
        trend_data=repository_trend_data,
        summary_data=summary_data,
        color_data="Repository",
        interval=time_interval,
        sub_title="All repositories",
    )
    repository_trend_chart.write_html(output_dir / "repository_trend_chart.html")

    console.print_h1("# LOC Analyze")
    print(Cursor.UP() + Cursor.FORWARD(50) + Fore.GREEN + "FINISH")


if __name__ == "__main__":
    main()
