"""
Shared x-axis tick policy for Plotly LOC charts.

Description:
    Centralizes date interval normalization and readable tick selection.
    Uses the actual date span so sparse weekly data over a long range does
    not render one label per week.
Functions:
        build_client_tick_policy: Return JSON-safe policy data for report JavaScript.
                Keeps HTML chart rendering aligned with Python chart rendering.
        normalize_interval_label: Normalize analyzer and CLI interval labels.
                Converts Date/Week/Month and daily/weekly/monthly into one vocabulary.
        resolve_xaxis_tick_config: Resolve a Plotly tick format and dtick.
                Uses date span and point count to avoid overcrowded x-axis labels.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class _TickRule:
    max_span: int | None
    tickformat: str
    dtick: str

    def as_payload(self) -> dict[str, int | str | None]:
        return {
            "max_span": self.max_span,
            "tickformat": self.tickformat,
            "dtick": self.dtick,
        }


_INTERVAL_ALIASES = {
    "date": "daily",
    "daily": "daily",
    "week": "weekly",
    "weekly": "weekly",
    "month": "monthly",
    "monthly": "monthly",
}

_TICK_RULES = {
    "daily": (
        _TickRule(14, "%b %d", "D1"),
        _TickRule(45, "%b %d", "D7"),
        _TickRule(120, "%b %d", "D14"),
        _TickRule(370, "%b %Y", "M1"),
        _TickRule(None, "%b %Y", "M3"),
    ),
    "weekly": (
        _TickRule(26, "%b %d", "W1"),
        _TickRule(104, "%b %Y", "M1"),
        _TickRule(None, "%b %Y", "M3"),
    ),
    "monthly": (
        _TickRule(24, "%b %Y", "M1"),
        _TickRule(72, "%b %Y", "M3"),
        _TickRule(None, "%Y", "M6"),
    ),
}


def build_client_tick_policy() -> dict[str, Any]:
    """
    Return JSON-safe x-axis tick policy data for browser-rendered charts.
    """
    return {
        "aliases": _INTERVAL_ALIASES,
        "rules": {
            interval: [rule.as_payload() for rule in rules]
            for interval, rules in _TICK_RULES.items()
        },
    }


def normalize_interval_label(interval_label: str) -> str:
    """
    Normalize supported interval labels to daily, weekly, or monthly.
    """
    label = str(interval_label or "").lower()
    return _INTERVAL_ALIASES.get(label, label)


def resolve_xaxis_tick_config(
    interval_label: str,
    *,
    values: Iterable[object] | None = None,
    point_count: int = 0,
) -> tuple[str, str]:
    """
    Resolve a Plotly tick format and dtick for a date x-axis.
    """
    interval = normalize_interval_label(interval_label)
    effective_span = max(
        _calculate_interval_span(interval, values),
        _coerce_point_count(point_count),
    )
    rules = _TICK_RULES.get(interval, ())
    for rule in rules:
        if rule.max_span is None or effective_span <= rule.max_span:
            return rule.tickformat, rule.dtick
    return "%b %Y", "M1"


def _coerce_point_count(point_count: int) -> int:
    try:
        return max(int(point_count), 0)
    except (TypeError, ValueError):
        return 0


def _calculate_interval_span(
    interval: str, values: Iterable[object] | None
) -> int:
    if values is None:
        return 0
    raw_values = list(values)
    if not raw_values:
        return 0
    dates = pd.to_datetime(pd.Series(raw_values), errors="coerce").dropna()
    if dates.empty:
        return 0
    first = dates.min()
    last = dates.max()
    if interval == "monthly":
        return (last.year - first.year) * 12 + last.month - first.month + 1
    day_span = int((last - first).total_seconds() // 86400) + 1
    day_span = max(day_span, 1)
    if interval == "weekly":
        return ((day_span - 1) // 7) + 1
    return day_span
