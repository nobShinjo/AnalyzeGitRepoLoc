"""Tests for shared chart tick policy."""

from __future__ import annotations

# pylint: disable=missing-function-docstring

from analyze_git_repo_loc.reporting.chart_ticks import (
    build_client_tick_policy,
    normalize_interval_label,
    resolve_xaxis_tick_config,
    select_tick_values,
)


def test_weekly_tick_config_uses_month_ticks_for_sparse_long_span() -> None:
    """Long weekly ranges should not render one x-axis label per week."""
    tickformat, dtick = resolve_xaxis_tick_config(
        "Week",
        values=["2024-04-01", "2026-02-23"],
        point_count=29,
    )

    assert tickformat == "%b %Y"
    assert dtick == "M1"


def test_daily_tick_config_uses_two_week_ticks_for_medium_span() -> None:
    """Medium daily ranges should use two-week ticks instead of dense labels."""
    tickformat, dtick = resolve_xaxis_tick_config(
        "Date",
        values=["2026-01-01", "2026-04-30"],
        point_count=120,
    )

    assert tickformat == "%b %d"
    assert dtick == "D14"


def test_interval_label_aliases_match_cli_labels() -> None:
    """Analyzer and CLI interval labels should normalize consistently."""
    assert normalize_interval_label("Date") == "daily"
    assert normalize_interval_label("daily") == "daily"
    assert normalize_interval_label("Week") == "weekly"
    assert normalize_interval_label("weekly") == "weekly"
    assert normalize_interval_label("Month") == "monthly"
    assert normalize_interval_label("monthly") == "monthly"


def test_client_tick_policy_is_json_safe_and_span_based() -> None:
    """HTML reports should receive the same span-based policy data."""
    policy = build_client_tick_policy()

    assert policy["aliases"]["week"] == "weekly"
    assert policy["rules"]["weekly"][0] == {
        "max_span": 26,
        "tickformat": "%b %d",
        "dtick": "W1",
    }
    assert policy["rules"]["weekly"][1] == {
        "max_span": 104,
        "tickformat": "%b %Y",
        "dtick": "M1",
    }
    assert policy["max_tick_labels"] == 10


def test_select_tick_values_caps_dense_date_labels() -> None:
    """Dense date ranges should render a bounded number of x-axis labels."""
    values = [f"2026-01-{day:02d}" for day in range(1, 30)]

    selected = select_tick_values(values, max_labels=10)

    assert len(selected) <= 10
    assert selected[0] == "2026-01-01"
    assert selected[-1] == "2026-01-29"
