"""
Shared analysis helpers for trend and summary datasets.

Description:
    Provides data preparation helpers used by chart and report generation.
    Aggregates NLOC data into trend tables and summary tables.
    Keeps the logic small and reusable across outputs.
Functions:
	prepare_trend_data: Build trend data for charts.
		Aggregates NLOC by interval and category for stacked series.
	prepare_summary_data: Build summary data for charts.
		Calculates totals, cumulative sums, and diffs by interval.
	prepare_author_contribution_data: Build author contribution data for charts.
		Summarizes author totals per repository for contribution charts.
"""

from __future__ import annotations

import pandas as pd


def prepare_trend_data(
    data: pd.DataFrame, time_interval: str, category_column: str
) -> pd.DataFrame:
    """
    Prepare trend data for trend charts.

    Args:
        data (pd.DataFrame): The data to prepare the trend.
        time_interval (str): The interval to group by.
        category_column (str): The column name to group by.

    Returns:
        pd.DataFrame: The trend data for the trend chart.
    """
    grouped_data = (
        data.sort_values(by=[time_interval, category_column])
        .groupby([time_interval, category_column], as_index=False)["NLOC"]
        .sum()
    )
    grouped_data["SUM"] = grouped_data.groupby(category_column)["NLOC"].cumsum()
    trend_data = (
        grouped_data.pivot(index=time_interval, columns=category_column, values="SUM")
        .reset_index()
        .ffill()
    )
    if trend_data.empty:
        return trend_data
    sorted_columns = (
        trend_data.iloc[-1, 1:]
        .infer_objects(copy=False)
        .sort_values(ascending=False)
        .index.tolist()
    )
    return trend_data.loc[:, [time_interval] + sorted_columns]


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
            Added=pd.NamedAgg(column="NLOC_Added", aggfunc="sum"),
            Deleted=pd.NamedAgg(column="NLOC_Deleted", aggfunc="sum"),
            NLOC=pd.NamedAgg(column="NLOC", aggfunc="sum"),
        )
        .reset_index()
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
    contribution_data = data.groupby(["Author", "Repository"], as_index=False)["NLOC"].sum()
    summary_data = contribution_data.pivot(
        index="Author", columns="Repository", values="NLOC"
    ).fillna(0)
    if summary_data.empty:
        return summary_data.reset_index()
    sorted_columns = (
        summary_data.iloc[-1]
        .infer_objects(copy=False)
        .sort_values(ascending=False)
        .index.tolist()
    )
    summary_data = summary_data[sorted_columns].reset_index()
    summary_data["Total"] = summary_data.iloc[:, 1:].sum(axis=1)
    summary_data = (
        summary_data.sort_values(by="Total", ascending=False)
        .drop(columns="Total")
        .reset_index(drop=True)
    )
    return summary_data
