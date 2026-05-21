"""Tests for generated HTML report behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from analyze_git_repo_loc.html_report import generate_html_report


class HtmlReportUxTests(unittest.TestCase):
    """Generated report UX structure tests."""

    def test_report_uses_lazy_tab_rendering_markers(self) -> None:
        html = self._generate_report_html()

        self.assertIn('data-report-shell="true"', html)
        self.assertIn('data-report-table="true"', html)
        self.assertIn('data-report-chart="true"', html)
        self.assertIn("const renderedTabs = new Set();", html)
        self.assertIn("const ensureTabRendered = (tabId)", html)
        self.assertIn("const renderActiveTab = ()", html)
        self.assertIn('ensureTabRendered("overview");', html)
        self.assertNotIn("renderAllCharts();", html)
        self.assertNotIn("renderAllTables();", html)

    def test_report_has_bounded_dashboard_and_filter_feedback(self) -> None:
        html = self._generate_report_html()

        self.assertIn("report-hero", html)
        self.assertIn("metric-grid", html)
        self.assertIn("chart-panel", html)
        self.assertIn("tag-count", html)
        self.assertIn("data-tag-count", html)
        self.assertIn("max-height: 14rem", html)
        self.assertIn("overflow-x: auto", html)

    def _generate_report_html(self) -> str:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            generate_html_report(
                output_dir=output_dir,
                charts_root=None,
                time_interval="Month",
                language_analysis=self._language_analysis(),
                author_analysis=self._author_analysis(),
                repository_trend_analysis=self._repository_trend_analysis(),
                detail_analysis=self._detail_analysis(),
            )
            return (output_dir / "report.html").read_text(encoding="utf-8")

    @staticmethod
    def _repository_trend_analysis() -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "Month": "2026-01-01",
                    "Repository": "alpha-service-with-a-very-long-name",
                    "NLOC_Added": 120,
                    "NLOC_Deleted": 20,
                    "NLOC": 100,
                },
                {
                    "Month": "2026-02-01",
                    "Repository": "beta-platform",
                    "NLOC_Added": 80,
                    "NLOC_Deleted": 10,
                    "NLOC": 70,
                },
            ]
        )

    @staticmethod
    def _language_analysis() -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "Month": "2026-01-01",
                    "Repository": "alpha-service-with-a-very-long-name",
                    "Language": "Python",
                    "NLOC_Added": 90,
                    "NLOC_Deleted": 10,
                    "NLOC": 80,
                },
                {
                    "Month": "2026-02-01",
                    "Repository": "beta-platform",
                    "Language": "TypeScript",
                    "NLOC_Added": 80,
                    "NLOC_Deleted": 10,
                    "NLOC": 70,
                },
            ]
        )

    @staticmethod
    def _author_analysis() -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "Month": "2026-01-01",
                    "Repository": "alpha-service-with-a-very-long-name",
                    "Author": "Nob Shinjo",
                    "NLOC_Added": 120,
                    "NLOC_Deleted": 20,
                    "NLOC": 100,
                },
                {
                    "Month": "2026-02-01",
                    "Repository": "beta-platform",
                    "Author": "Long Author Name For Layout Safety",
                    "NLOC_Added": 80,
                    "NLOC_Deleted": 10,
                    "NLOC": 70,
                },
            ]
        )

    @staticmethod
    def _detail_analysis() -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "Month": "2026-01-01",
                    "Repository": "alpha-service-with-a-very-long-name",
                    "Author": "Nob Shinjo",
                    "Language": "Python",
                    "NLOC_Added": 120,
                    "NLOC_Deleted": 20,
                    "NLOC": 100,
                },
                {
                    "Month": "2026-02-01",
                    "Repository": "beta-platform",
                    "Author": "Long Author Name For Layout Safety",
                    "Language": "TypeScript",
                    "NLOC_Added": 80,
                    "NLOC_Deleted": 10,
                    "NLOC": 70,
                },
            ]
        )
