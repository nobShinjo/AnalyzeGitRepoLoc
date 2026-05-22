"""Tests for Plotly chart configuration."""

from __future__ import annotations

import pandas as pd

from analyze_git_repo_loc.chart_builder import ChartBuilder, ChartStrategy


def _trend_data(interval: str, dates: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({interval: dates, "Python": range(len(dates))})


def _summary_data(interval: str, dates: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        {
            interval: dates,
            "SUM": range(len(dates)),
            "Diff": [1] * len(dates),
            "Added": [2] * len(dates),
            "Deleted": [-1] * len(dates),
        }
    )


def test_weekly_trend_chart_uses_span_based_ticks_for_sparse_long_ranges() -> None:
    """Weekly charts should account for the date span, not only point count."""
    dates = pd.date_range("2024-04-01", periods=29, freq="25D")

    fig = (
        ChartBuilder()
        .set_strategy(ChartStrategy.TREND)
        .build(
            trend_data=_trend_data("Week", dates),
            summary_data=_summary_data("Week", dates),
            interval="Week",
            title="Weekly trend",
        )
    )

    assert fig.layout.xaxis.dtick == "M1"
    assert fig.layout.xaxis.tickformat == "%b %Y"


def test_daily_trend_chart_uses_sparse_ticks_for_medium_ranges() -> None:
    """Daily charts should not render one label per day on medium reports."""
    dates = pd.date_range("2026-01-01", periods=120, freq="D")

    fig = (
        ChartBuilder()
        .set_strategy(ChartStrategy.TREND)
        .build(
            trend_data=_trend_data("Date", dates),
            summary_data=_summary_data("Date", dates),
            interval="Date",
            title="Daily trend",
        )
    )

    assert fig.layout.xaxis.dtick == "D14"
    assert fig.layout.xaxis.tickformat == "%b %d"
