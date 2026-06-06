"""Tests for Plotly chart configuration."""

from __future__ import annotations

# pylint: disable=missing-function-docstring

import warnings
from typing import cast

import pandas as pd

from analyze_git_repo_loc.reporting.chart_builder import ChartBuilder, ChartStrategy


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

    xaxis = cast(dict[str, object], fig.layout.to_plotly_json()["xaxis"])

    assert xaxis["dtick"] == "M1"
    assert xaxis["tickformat"] == "%b %Y"


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

    xaxis = cast(dict[str, object], fig.layout.to_plotly_json()["xaxis"])
    tickvals = cast(list[object], xaxis["tickvals"])

    assert xaxis["dtick"] == "D14"
    assert xaxis["tickformat"] == "%b %d"
    assert xaxis["tickmode"] == "array"
    assert len(tickvals) <= 10
    assert tickvals[0] == dates[0]
    assert tickvals[-1] == dates[-1]


def test_trend_chart_build_does_not_emit_plotly_deprecation_warning() -> None:
    """Chart generation should avoid deprecated Plotly append_trace calls."""
    dates = pd.date_range("2026-01-01", periods=3, freq="D")

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        ChartBuilder().set_strategy(ChartStrategy.TREND).build(
            trend_data=_trend_data("Date", dates),
            summary_data=_summary_data("Date", dates),
            interval="Date",
            title="Daily trend",
        )
