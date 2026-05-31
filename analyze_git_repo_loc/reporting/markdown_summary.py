"""
Markdown summary generator for analysis results.

Functions:
    generate_markdown_summary(
        output_dir: Path,
        time_interval: str,
        language_analysis: pd.DataFrame,
        author_analysis: pd.DataFrame,
        repository_trend_analysis: pd.DataFrame,
    ) -> None:
        Generate a Markdown summary file in the run output directory.

Overview:
    Builds a lightweight Markdown report that summarizes totals and the top
    entities for languages, authors, and repositories.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_NO_DATA_MESSAGE = "_No data available._"


def _format_markdown_table(
    headers: list[str],
    rows: list[list[str]],
    alignments: list[str] | None = None,
) -> str:
    """
    Format a Markdown table from headers and rows.

    Args:
        headers (list[str]): Table header values.
        rows (list[list[str]]): Table rows.
        alignments (list[str] | None): Column alignments ("left" or "right").

    Returns:
        str: Markdown-formatted table or placeholder text if empty.
    """
    if not rows:
        return _NO_DATA_MESSAGE
    if alignments is None:
        alignments = ["left"] * len(headers)
    if len(alignments) != len(headers):
        raise ValueError("Alignments must match the number of headers.")
    header_line = "| " + " | ".join(headers) + " |"
    separator_cells = []
    for alignment in alignments:
        if alignment == "right":
            separator_cells.append("---:")
        else:
            separator_cells.append(":---")
    separator_line = "| " + " | ".join(separator_cells) + " |"
    row_lines = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_line, separator_line] + row_lines)


def _to_int(value: object) -> int:
    """
    Convert a value to int safely.

    Args:
        value (object): Value to convert.

    Returns:
        int: Converted integer value.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _format_number(value: object) -> str:
    """
    Format numeric values with a thousands separator.

    Args:
        value (object): Value to format.

    Returns:
        str: Formatted number string.
    """
    return f"{_to_int(value):,}"


def _summarize_category(
    analysis: pd.DataFrame, category_column: str, top_n: int = 10
) -> str:
    """
    Build a Markdown table for a summary category.

    Args:
        analysis (pd.DataFrame): Aggregated analysis data.
        category_column (str): Column to summarize.
        top_n (int): Number of rows to include.

    Returns:
        str: Markdown table or placeholder text.
    """
    if analysis.empty or category_column not in analysis.columns:
        return _NO_DATA_MESSAGE
    summary = (
        analysis.groupby(category_column)[["NLOC_Added", "NLOC_Deleted", "NLOC"]]
        .sum()
        .reset_index()
    )
    summary[category_column] = summary[category_column].fillna("Unknown")
    summary = summary.sort_values(by="NLOC", ascending=False).head(top_n)
    rows = [
        [
            str(row[category_column]),
            _format_number(row["NLOC_Added"]),
            _format_number(row["NLOC_Deleted"]),
            _format_number(row["NLOC"]),
        ]
        for _, row in summary.iterrows()
    ]
    return _format_markdown_table(
        ["Name", "Added", "Deleted", "NLOC"],
        rows,
        ["left", "right", "right", "right"],
    )


def _summarize_totals(repository_trend_analysis: pd.DataFrame) -> str:
    """
    Build a Markdown table for overall totals.

    Args:
        repository_trend_analysis (pd.DataFrame): Repository trend data.

    Returns:
        str: Markdown table or placeholder text.
    """
    if repository_trend_analysis.empty:
        return _NO_DATA_MESSAGE
    totals = repository_trend_analysis[["NLOC_Added", "NLOC_Deleted", "NLOC"]].sum()
    rows = [
        [
            _format_number(totals["NLOC_Added"]),
            _format_number(totals["NLOC_Deleted"]),
            _format_number(totals["NLOC"]),
        ]
    ]
    return _format_markdown_table(
        ["Added", "Deleted", "NLOC"],
        rows,
        ["right", "right", "right"],
    )


def generate_markdown_summary(
    output_dir: Path,
    time_interval: str,
    language_analysis: pd.DataFrame,
    author_analysis: pd.DataFrame,
    repository_trend_analysis: pd.DataFrame,
) -> None:
    """
    Generate a Markdown summary file for the analysis run.

    Args:
        output_dir (Path): Output directory for the run.
        time_interval (str): Time interval for aggregation.
        language_analysis (pd.DataFrame): Language analysis data.
        author_analysis (pd.DataFrame): Author analysis data.
        repository_trend_analysis (pd.DataFrame): Repository trend data.
    """
    repositories = (
        sorted(repository_trend_analysis["Repository"].dropna().unique())
        if not repository_trend_analysis.empty
        and "Repository" in repository_trend_analysis.columns
        else []
    )
    lines = [
        "# Analysis Summary",
        "",
        f"- Run directory: `{output_dir.name}`",
        f"- Time interval: `{time_interval}`",
        f"- Repositories analyzed: {len(repositories)}",
    ]
    if repositories:
        lines.append(f"- Repository list: {', '.join(repositories)}")

    lines.extend(
        [
            "",
            "## Totals",
            _summarize_totals(repository_trend_analysis),
            "",
            "## Languages (Top 10 by NLOC)",
            _summarize_category(language_analysis, "Language"),
            "",
            "## Authors (Top 10 by NLOC)",
            _summarize_category(author_analysis, "Author"),
            "",
            "## Repositories (Top 10 by NLOC)",
            _summarize_category(repository_trend_analysis, "Repository"),
        ]
    )

    summary_path = output_dir / "summary.md"
    with open(summary_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
