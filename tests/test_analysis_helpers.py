"""Tests for analysis helper warning behavior."""

from __future__ import annotations

import warnings

import pandas as pd

from analyze_git_repo_loc.analysis.analysis_helpers import (
    prepare_author_contribution_data,
    prepare_trend_data,
)


def test_prepare_trend_data_emits_no_future_compatibility_warning() -> None:
    """Trend preparation should avoid pandas copy deprecation warnings."""
    data = pd.DataFrame(
        {
            "Date": ["2026-01", "2026-01", "2026-02", "2026-02"],
            "Repository": ["alpha", "beta", "alpha", "beta"],
            "NLOC": [10, 30, 20, 15],
        }
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        trend_data = prepare_trend_data(data, "Date", "Repository")

    assert list(trend_data.columns) == ["Date", "beta", "alpha"]


def test_prepare_author_contribution_data_emits_no_future_compatibility_warning() -> None:
    """Author contribution preparation should avoid pandas copy deprecation warnings."""
    data = pd.DataFrame(
        {
            "Author": ["Ann", "Ann", "Bob", "Bob"],
            "Repository": ["alpha", "beta", "alpha", "beta"],
            "NLOC": [10, 5, 7, 20],
        }
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        contribution_data = prepare_author_contribution_data(data)

    assert list(contribution_data.columns) == ["Author", "beta", "alpha"]
