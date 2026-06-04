"""Tests for generated HTML report behavior."""

from __future__ import annotations

# pylint: disable=missing-function-docstring,protected-access

import tempfile
import unittest
import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from analyze_git_repo_loc import __main__ as main_module
from analyze_git_repo_loc.reporting.html_report import generate_html_report


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

    def test_repository_list_is_rendered_as_a_list_not_a_metric_string(self) -> None:
        html = self._generate_report_html()

        self.assertIn('class="repository-list"', html)
        self.assertIn("<li>alpha-service-with-a-very-long-name</li>", html)
        self.assertIn("<li>beta-platform</li>", html)
        self.assertNotIn(
            '<div class="metric-label">Repository list</div>',
            html,
        )
        self.assertNotIn(
            "alpha-service-with-a-very-long-name, beta-platform",
            html,
        )

    def test_daily_x_axis_uses_adaptive_tick_config(self) -> None:
        html = self._generate_report_html(time_interval="Date")

        self.assertIn("const getTickConfig = (intervalLabel, intervalValues)", html)
        self.assertIn("const getIntervalSpan = (intervalLabel, intervalValues)", html)
        self.assertIn("const getTickValues = (intervalValues)", html)
        self.assertIn("getTickConfig(reportData.time_interval, intervalValues)", html)
        self.assertIn("layout.xaxis.tickmode = \"array\";", html)
        self.assertIn("layout.xaxis.tickvals = tickConfig.tickvals;", html)
        self.assertIn('"tick_policy"', html)
        self.assertNotIn('return { tickformat: "%b %d, %Y", dtick: "D1" };', html)

    def test_weekly_x_axis_uses_span_based_tick_policy(self) -> None:
        html = self._generate_report_html(time_interval="Week")

        self.assertIn('"weekly"', html)
        self.assertIn('"max_span": 104', html)
        self.assertIn('"max_tick_labels": 10', html)
        self.assertIn('"dtick": "W1"', html)
        self.assertNotIn(
            'return { tickformat: "%b %d, %Y", dtick: "W1" };',
            html,
        )

    def test_tab_rendering_queues_chart_work_after_content_render(self) -> None:
        html = self._generate_report_html()

        self.assertIn("const chartRenderQueue = [];", html)
        self.assertIn("const queueChartRender = (tabId)", html)
        self.assertIn("queueChartRender(tabId);", html)
        self.assertNotIn("renderChartsForTab(tabId);\n        renderedTabs.add(tabId);", html)

    def test_repo_tab_lists_exclude_template_summary(self) -> None:
        html = self._generate_report_html(
            exclude_metadata=[
                {
                    "repository": "alpha-service-with-a-very-long-name",
                    "mode": "auto",
                    "templates": ["Python Project", "Node.js Project"],
                    "excluded_paths": ["node_modules", ".venv"],
                    "template_paths": ["node_modules", ".venv"],
                }
            ]
        )

        self.assertIn("Exclude Paths", html)
        self.assertIn("Python Project, Node.js Project", html)
        self.assertIn('<td class="text-start">auto</td>', html)
        self.assertIn(
            '<td class="text-start">Python Project, Node.js Project</td>',
            html,
        )
        self.assertIn("node_modules", html)
        self.assertIn(".venv", html)
        self.assertIn("exclude-path-list", html)
        self.assertIn('class="exclude-path-list list-unstyled text-start mb-0"', html)
        self.assertIn('class="exclude-path-cell text-start"', html)
        self.assertIn(".report-content .exclude-path-list code", html)
        self.assertIn("text-align: left;", html)
        self.assertIn("<code>node_modules</code>", html)
        self.assertIn("<code>.venv</code>", html)
        self.assertNotIn("node_modules, .venv", html)

    def test_generate_report_passes_exclude_metadata_to_html_builder(self) -> None:
        progress_context = MagicMock()
        exclude_metadata = [{"repository": "alpha", "excluded_paths": [".venv"]}]

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(main_module, "tqdm", return_value=progress_context):
                with patch.object(main_module, "generate_html_report") as report:
                    main_module._generate_report(
                        output_dir=Path(tmp_dir),
                        output_root=Path(tmp_dir),
                        time_interval="Month",
                        loc_data_repositories=[],
                        language_analysis=pd.DataFrame(),
                        author_analysis=pd.DataFrame(),
                        repository_trend_analysis=pd.DataFrame(),
                        exclude_metadata=exclude_metadata,
                    )

        self.assertEqual(report.call_args.kwargs["exclude_metadata"], exclude_metadata)

    def test_main_passes_analyzed_exclude_metadata_to_report(self) -> None:
        args = argparse.Namespace(
            command="run",
            output=Path("out"),
            interval="monthly",
            no_plot_show=True,
        )
        exclude_metadata = [
            {
                "repository": "alpha",
                "mode": "auto",
                "templates": ["Python Project"],
                "excluded_paths": [".venv"],
            }
        ]
        loc_data = pd.DataFrame({"Repository": ["alpha"], "Branch": ["main"]})
        analysis = pd.DataFrame(
            {
                "Month": ["2026-01-01"],
                "Repository": ["alpha"],
                "NLOC_Added": [1],
                "NLOC_Deleted": [0],
                "NLOC": [1],
            }
        )

        def analyze_stub(parsed_args: argparse.Namespace) -> list[pd.DataFrame]:
            parsed_args.exclude_metadata = exclude_metadata
            return [loc_data]

        with patch.object(main_module, "parse_arguments", return_value=args):
            with patch.object(main_module, "_apply_interactive_repository_selection"):
                with patch.object(main_module, "_print_start"):
                    with patch.object(
                        main_module,
                        "analyze_git_repositories",
                        side_effect=analyze_stub,
                    ):
                        with patch.object(
                            main_module,
                            "get_time_interval_and_period",
                            return_value=("Month", "ME"),
                        ):
                            with patch.object(
                                main_module,
                                "_build_analysis_data",
                                return_value=(analysis, analysis, analysis),
                            ):
                                with patch.object(main_module, "_save_analysis_outputs"):
                                    with patch.object(main_module, "_generate_charts"):
                                        with patch.object(
                                            main_module, "_generate_report"
                                        ) as report:
                                            with patch.object(
                                                main_module, "_maybe_open_report"
                                            ):
                                                with patch.object(
                                                    main_module,
                                                    "_print_output_summary",
                                                ):
                                                    main_module.main()

        self.assertEqual(report.call_args.kwargs["exclude_metadata"], exclude_metadata)

    def test_main_does_not_pass_exclude_metadata_to_save_outputs(self) -> None:
        args = argparse.Namespace(
            command="run",
            output=Path("out"),
            interval="monthly",
            no_plot_show=True,
        )
        loc_data = pd.DataFrame({"Repository": ["alpha"], "Branch": ["main"]})
        analysis = pd.DataFrame(
            {
                "Month": ["2026-01-01"],
                "Repository": ["alpha"],
                "NLOC_Added": [1],
                "NLOC_Deleted": [0],
                "NLOC": [1],
            }
        )

        def save_stub(
            *,
            output_dir: Path,
            args: argparse.Namespace,
            time_interval: str,
            language_analysis: pd.DataFrame,
            author_analysis: pd.DataFrame,
            repository_trend_analysis: pd.DataFrame,
        ) -> None:
            raise RuntimeError("stop after save")

        with patch.object(main_module, "parse_arguments", return_value=args):
            with patch.object(main_module, "_apply_interactive_repository_selection"):
                with patch.object(main_module, "_print_start"):
                    with patch.object(
                        main_module,
                        "analyze_git_repositories",
                        return_value=[loc_data],
                    ):
                        with patch.object(
                            main_module,
                            "get_time_interval_and_period",
                            return_value=("Month", "ME"),
                        ):
                            with patch.object(
                                main_module,
                                "_build_analysis_data",
                                return_value=(analysis, analysis, analysis),
                            ):
                                with patch.object(
                                    main_module,
                                    "_save_analysis_outputs",
                                    side_effect=save_stub,
                                ):
                                    with self.assertRaisesRegex(
                                        RuntimeError, "stop after save"
                                    ):
                                        main_module.main()

    def _generate_report_html(
        self,
        *,
        time_interval: str = "Month",
        exclude_metadata: list[dict[str, object]] | None = None,
    ) -> str:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            language_analysis = self._language_analysis().rename(
                columns={"Month": time_interval}
            )
            author_analysis = self._author_analysis().rename(
                columns={"Month": time_interval}
            )
            repository_trend_analysis = self._repository_trend_analysis().rename(
                columns={"Month": time_interval}
            )
            detail_analysis = self._detail_analysis().rename(
                columns={"Month": time_interval}
            )
            generate_html_report(
                output_dir=output_dir,
                charts_root=None,
                time_interval=time_interval,
                language_analysis=language_analysis,
                author_analysis=author_analysis,
                repository_trend_analysis=repository_trend_analysis,
                detail_analysis=detail_analysis,
                exclude_metadata=exclude_metadata,
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
