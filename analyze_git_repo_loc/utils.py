"""
This module provides utility functions for analyzing lines of code (LOC) in Git repositories.
Functions:
    parse_arguments(parser: argparse.ArgumentParser) -> argparse.Namespace:
        Parse command line arguments.
    process_loc_data(
        Process LOC data and save data and charts.
"""

import argparse
from pathlib import Path

import pandas as pd


def parse_arguments(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """
    parse_arguments Parse command line arguments.

    Args:
        parser (ArgumentParser): ArgumentParser object.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """

    # pylint: enable=line-too-long
    parser.add_argument(
        "repo_paths",
        type=lambda s: [Path(item) for item in s.split(",")],
        help="Comma-separated list of Git repository paths",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default="./out", help="Output path"
    )
    parser.add_argument(
        "-s", "--start_date", type=str, default=None, help="Start Date yyyy-mm-dd"
    )
    parser.add_argument(
        "-e", "--end_date", type=str, default=None, help="End Date yyyy-mm-dd"
    )
    parser.add_argument(
        "-b", "--branch", type=str, default="main", help="Branch name (default: main)"
    )
    parser.add_argument(
        "--interval",
        choices=["daily", "weekly", "monthly"],
        default="monthly",
        help="Interval (default: monthly)",
    )
    parser.add_argument(
        "--lang",
        type=lambda s: [item.strip() for item in s.split(",")],
        default=None,
        help="Count only the given space separated, case-insensitive languages L1,L2,L3, etc. \n \
        Use 'cloc --show-lang' to see the list of recognized languages.",
    )
    parser.add_argument(
        "--author-name",
        type=str,
        default=None,
        help="Author name to filter commits",
    )
    parser.add_argument(
        "--clear_cache",
        action="store_true",
        help="If set, the cache will be cleared before executing the main function.",
    )

    return parser.parse_args()


def process_loc_data(
    loc_data: pd.DataFrame, output_path: Path, analyzer, interval: str
):
    """
    process_loc_data Process LOC data and save data and charts.

    Args:
        loc_data (pd.DataFrame): Data of LOC by language and author.
        output_path (Path): The path to save the data and charts.
        analyzer (_type_): analyzer object to save data and create charts.
        interval (str): The interval to use for formatting the x-axis ticks.
    """

    # Pivot table by language
    loc_trend_by_language = loc_data.pivot_table(
        index="Date", columns="Language", values="code", aggfunc="sum", fill_value=0
    ).astype(int)

    if not loc_trend_by_language.empty:
        loc_trend_by_language.sort_values(
            by=loc_trend_by_language.index[-1],
            axis=1,
            ascending=False,
            inplace=True,
        )

    # Pivot table by author
    loc_trend_by_author = loc_data.pivot_table(
        index="Date", columns="Author", values="code", aggfunc="sum", fill_value=0
    ).astype(int)

    if not loc_trend_by_author.empty:
        loc_trend_by_author.sort_values(
            by=loc_trend_by_author.index[-1],
            axis=1,
            ascending=False,
            inplace=True,
        )

    # Total LOC trend
    trend_of_total_loc = loc_trend_by_language.copy(deep=True)
    trend_of_total_loc["SUM"] = trend_of_total_loc.sum(axis=1)
    trend_of_total_loc = trend_of_total_loc[["SUM"]]
    trend_of_total_loc["Diff"] = trend_of_total_loc["SUM"].diff()

    # Save data and charts for the repository
    analyzer.save_dataframe(loc_data, output_path / "loc_data.csv")
    analyzer.save_dataframe(
        loc_trend_by_language, output_path / "loc_trend_by_language.csv"
    )
    analyzer.save_dataframe(
        loc_trend_by_author, output_path / "loc_trend_by_author.csv"
    )
    analyzer.save_dataframe(trend_of_total_loc, output_path / "trend_of_total_loc.csv")

    analyzer.create_charts(
        language_trend_data=loc_trend_by_language,
        author_trend_data=loc_trend_by_author,
        sum_data=trend_of_total_loc,
        output_path=output_path,
        interval=interval,
    )
    analyzer.save_charts(output_path)
