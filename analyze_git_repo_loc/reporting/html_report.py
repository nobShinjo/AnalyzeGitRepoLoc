"""
HTML report generator for LOC analysis runs.

Description:
    Builds a single HTML report with bundled assets and embedded Plotly charts.
    Renders a Tabler-style layout with overview and repository tabs.
    Writes report.html and assets into the analysis output directory.
Classes:
        ProgressEvent: Progress update for HTML report generation.
                Carries parent/child progress bar details.
        HtmlReportBuilder: Build HTML reports for a single analysis run.
                Prepares assets and renders templates with analysis data.
Functions:
        generate_html_report: Generate a report.html file in the run output directory.
                Creates an HtmlReportBuilder and writes outputs to disk.
Methods:
        HtmlReportBuilder.generate: Write assets and the HTML report to disk.
                Copies bundled assets and emits report.html.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypeAlias

import pandas as pd
import plotly.io as pio
from jinja2 import Environment, FileSystemLoader, select_autoescape
from plotly.offline import get_plotlyjs

from analyze_git_repo_loc.analysis_helpers import (
    prepare_author_contribution_data,
    prepare_summary_data,
    prepare_trend_data,
)
from analyze_git_repo_loc.reporting.chart_builder import ChartBuilder, ChartStrategy
from analyze_git_repo_loc.reporting.chart_ticks import build_client_tick_policy
from analyze_git_repo_loc.i18n import tr

_ASSETS_DIR_NAME = "assets"
_NO_DATA_MESSAGE = '<p class="text-muted">No data available.</p>'
_LANGUAGE_CHART_FILENAME = "language_chart.html"
_AUTHOR_CHART_FILENAME = "author_chart.html"
_REPOSITORY_CHART_FILENAME = "repository_chart.html"
_AUTHOR_CONTRIBUTION_CHART_FILENAME = "author_contribution_contribution_chart.html"
_FILTER_PROGRESS_CHUNK = 1000
_PARENT_PROGRESS_STEPS = 4
_LABEL_REPO_TABS = "Repo tabs"
_LABEL_FILTER_ROWS = "Filter rows"


@dataclass(frozen=True)
class ProgressEvent:
    """
    Progress update for HTML report generation.
    """

    label: str
    advance: int = 0
    total: int | None = None
    kind: str = "parent"
    done: bool = False


ProgressCallback: TypeAlias = Callable[[ProgressEvent], None]


class HtmlReportBuilder:
    """
    Build HTML reports for a single analysis run.
    """

    def __init__(
        self,
        *,
        output_dir: Path,
        charts_root: Path | None,
        time_interval: str,
        language_analysis: pd.DataFrame,
        author_analysis: pd.DataFrame,
        repository_trend_analysis: pd.DataFrame,
        detail_analysis: pd.DataFrame,
        exclude_metadata: list[dict[str, object]] | None = None,
    ) -> None:
        """
        Initialize the report builder with analysis data.
        """
        self.output_dir = output_dir
        self.charts_root = charts_root
        self.time_interval = time_interval
        self.language_analysis = language_analysis
        self.author_analysis = author_analysis
        self.repository_trend_analysis = repository_trend_analysis
        self.detail_analysis = detail_analysis
        self.exclude_metadata = exclude_metadata or []
        self._exclude_metadata_by_repo = {
            str(item.get("repository", "")): item for item in self.exclude_metadata
        }
        self._repo_chart_dirs = self._resolve_repo_chart_dirs()
        self.repositories = list(self._repo_chart_dirs.keys())
        package_dir = Path(__file__).resolve().parent
        self._template_dir = package_dir / "templates"
        if not self._template_dir.exists():
            self._template_dir = package_dir.parent / "templates"
        self._template_env = Environment(
            loader=FileSystemLoader(self._template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate(self, progress_callback: ProgressCallback | None = None) -> None:
        """
        Generate the HTML report and write it to the output directory.

        Args:
            progress_callback (ProgressCallback | None): Optional callback
                invoked after each report generation step.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_assets()
        report_html = self._build_report_html(progress_callback=progress_callback)
        (self.output_dir / "report.html").write_text(report_html, encoding="utf-8")
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(label=tr("progress.report_file_written"), advance=1)
            )

    def _ensure_assets(self) -> None:
        """
        Ensure bundled assets exist for the report output.
        """
        assets_dir = self.output_dir / _ASSETS_DIR_NAME
        css_source = self._template_dir / _ASSETS_DIR_NAME / "tabler.min.css"
        js_source = self._template_dir / _ASSETS_DIR_NAME / "tabler.min.js"
        assets_dir.mkdir(parents=True, exist_ok=True)
        (assets_dir / "tabler.min.css").write_text(
            css_source.read_text(encoding="utf-8").strip() + "\n",
            encoding="utf-8",
        )
        (assets_dir / "tabler.min.js").write_text(
            js_source.read_text(encoding="utf-8").strip() + "\n",
            encoding="utf-8",
        )
        (assets_dir / "plotly.min.js").write_text(
            get_plotlyjs() + "\n", encoding="utf-8"
        )

    def _resolve_repo_chart_dirs(self) -> dict[str, Path | None]:
        """
        Resolve repository names and associated chart directories.
        """
        repos_from_data = self._repositories_from_data()
        if repos_from_data:
            return self._map_repo_dirs(repos_from_data)
        if self.charts_root is None:
            return {}
        dirs = []
        for entry in self.charts_root.iterdir():
            if not entry.is_dir():
                continue
            if (entry / _LANGUAGE_CHART_FILENAME).exists() or (
                entry / _AUTHOR_CHART_FILENAME
            ).exists():
                dirs.append(entry)
        if dirs:
            return {entry.name: entry for entry in sorted(dirs)}
        if (self.charts_root / _LANGUAGE_CHART_FILENAME).exists() or (
            self.charts_root / _AUTHOR_CHART_FILENAME
        ).exists():
            return {self.charts_root.name: self.charts_root}
        return {}

    def _repositories_from_data(self) -> list[str]:
        """
        Extract repository names from analysis data.
        """
        if (
            self.repository_trend_analysis.empty
            or "Repository" not in self.repository_trend_analysis.columns
        ):
            return []
        return sorted(
            {
                str(name)
                for name in self.repository_trend_analysis["Repository"]
                .dropna()
                .unique()
                if str(name).strip()
            }
        )

    def _map_repo_dirs(self, repos: list[str]) -> dict[str, Path | None]:
        """
        Map repository names to chart directories when available.
        """
        if self.charts_root is None:
            return dict.fromkeys(repos, None)
        mapping = {repo: self.charts_root / repo for repo in repos}
        if len(repos) == 1:
            only_repo = repos[0]
            default_dir = self.charts_root
            repo_dir = self.charts_root / only_repo
            if not repo_dir.exists() and (
                (default_dir / _LANGUAGE_CHART_FILENAME).exists()
                or (default_dir / _AUTHOR_CHART_FILENAME).exists()
            ):
                mapping[only_repo] = default_dir
        return mapping

    def _build_report_html(
        self, *, progress_callback: ProgressCallback | None = None
    ) -> str:
        """
        Build the HTML report contents.
        """
        detail_data = self._aggregate_detail_analysis()
        template = self._template_env.get_template("report.html.j2")
        context = self._build_template_context(
            detail_data=detail_data,
            progress_callback=progress_callback,
            filter_chunk_size=_FILTER_PROGRESS_CHUNK,
        )
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(label=tr("progress.render_template"), advance=0)
            )
        rendered = template.render(**context)
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(label=tr("progress.render_template"), advance=1)
            )
        return rendered

    def _build_template_context(
        self,
        *,
        detail_data: pd.DataFrame,
        progress_callback: ProgressCallback | None = None,
        filter_chunk_size: int = _FILTER_PROGRESS_CHUNK,
    ) -> dict[str, object]:
        """
        Build the template context for rendering.
        """
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tab_ids = self._build_tab_ids(self.repositories)
        repo_tabs_meta = [{"id": tab_id, "name": repo} for repo, tab_id in tab_ids]
        tabs = [
            {"id": "overview", "label": "Overview", "active": True},
            *[
                {"id": tab_id, "label": repo, "active": False}
                for repo, tab_id in tab_ids
            ],
        ]
        overview = self._build_overview_context()
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    label=_LABEL_REPO_TABS,
                    advance=0,
                    total=_PARENT_PROGRESS_STEPS,
                )
            )
        repo_tabs = self._build_repo_tab_contexts(
            tab_ids, progress_callback=progress_callback
        )
        if progress_callback is not None:
            progress_callback(ProgressEvent(label=_LABEL_REPO_TABS, advance=1))
            progress_callback(ProgressEvent(label=_LABEL_FILTER_ROWS, advance=0))
        filter_payload = self._build_filter_payload(
            repo_tabs_meta,
            detail_data=detail_data,
            progress_callback=progress_callback,
            chunk_size=filter_chunk_size,
        )
        if progress_callback is not None:
            progress_callback(ProgressEvent(label=_LABEL_FILTER_ROWS, advance=1))
        return {
            "assets_dir": _ASSETS_DIR_NAME,
            "generated_at": generated_at,
            "tabs": tabs,
            "overview": overview,
            "repo_tabs": repo_tabs,
            "filter_data_json": self._serialize_filter_payload(filter_payload),
        }

    def _build_filter_payload(
        self,
        repo_tabs: list[dict[str, str]],
        *,
        detail_data: pd.DataFrame,
        progress_callback: ProgressCallback | None = None,
        chunk_size: int = _FILTER_PROGRESS_CHUNK,
    ) -> dict[str, object]:
        """
        Build the payload used for client-side report filtering.
        """
        rows = self._serialize_filter_rows(
            detail_data,
            progress_callback=progress_callback,
            chunk_size=chunk_size,
        )
        languages = sorted({row["language"] for row in rows})
        authors = sorted({row["author"] for row in rows})
        repositories = sorted({row["repository"] for row in rows})
        return {
            "time_interval": self.time_interval,
            "tick_policy": build_client_tick_policy(),
            "rows": rows,
            "languages": languages,
            "authors": authors,
            "repositories": repositories,
            "repo_tabs": repo_tabs,
        }

    def _aggregate_detail_analysis(self) -> pd.DataFrame:
        """
        Aggregate detailed analysis data for filter-driven reporting.
        """
        if self.detail_analysis.empty:
            return pd.DataFrame()
        required_columns = [
            self.time_interval,
            "Repository",
            "Author",
            "Language",
            "NLOC_Added",
            "NLOC_Deleted",
            "NLOC",
        ]
        if not set(required_columns).issubset(self.detail_analysis.columns):
            return pd.DataFrame()
        detail = self.detail_analysis[required_columns].copy()
        detail["Repository"] = detail["Repository"].fillna("Unknown").astype(str)
        detail["Author"] = detail["Author"].fillna("Unknown").astype(str)
        detail["Language"] = detail["Language"].fillna("Unknown").astype(str)
        grouped = (
            detail.groupby(
                [self.time_interval, "Repository", "Author", "Language"],
                as_index=False,
            )[["NLOC_Added", "NLOC_Deleted", "NLOC"]]
            .sum()
            .reset_index(drop=True)
        )
        grouped[self.time_interval] = grouped[self.time_interval].astype(str)
        return grouped

    def _serialize_filter_rows(
        self,
        detail_data: pd.DataFrame,
        *,
        progress_callback: ProgressCallback | None = None,
        chunk_size: int = _FILTER_PROGRESS_CHUNK,
    ) -> list[dict[str, object]]:
        """
        Serialize filter rows for embedding in the HTML report.
        """
        if detail_data.empty:
            if progress_callback is not None:
                progress_callback(
                    ProgressEvent(
                        label=_LABEL_FILTER_ROWS,
                        advance=0,
                        total=0,
                        kind="child",
                        done=True,
                    )
                )
            return []
        interval_col = self.time_interval
        total_rows = len(detail_data)
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    label=_LABEL_FILTER_ROWS,
                    advance=0,
                    total=total_rows,
                    kind="child",
                )
            )
        rows: list[dict[str, object]] = []
        for start in range(0, total_rows, chunk_size):
            end = min(start + chunk_size, total_rows)
            chunk = detail_data.iloc[start:end].copy()
            chunk = self._transform_filter_rows(chunk, interval_col)
            rows.extend(chunk.to_dict(orient="records"))
            if progress_callback is not None:
                progress_callback(
                    ProgressEvent(
                        label=_LABEL_FILTER_ROWS,
                        advance=len(chunk),
                        kind="child",
                    )
                )
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(label=_LABEL_FILTER_ROWS, kind="child", done=True)
            )
        return rows

    @staticmethod
    def _transform_filter_rows(
        detail_data: pd.DataFrame, interval_col: str
    ) -> pd.DataFrame:
        """
        Transform detail rows into filter payload rows.
        """
        columns = [
            interval_col,
            "Repository",
            "Author",
            "Language",
            "NLOC_Added",
            "NLOC_Deleted",
            "NLOC",
        ]
        chunk = detail_data.loc[:, columns].copy()
        chunk[interval_col] = chunk[interval_col].astype(str)
        chunk["Repository"] = chunk["Repository"].astype(str)
        chunk["Author"] = chunk["Author"].astype(str)
        chunk["Language"] = chunk["Language"].astype(str)
        for col in ["NLOC_Added", "NLOC_Deleted", "NLOC"]:
            chunk[col] = (
                pd.to_numeric(chunk[col], errors="coerce").fillna(0).astype(int)
            )
        return chunk.rename(
            columns={
                interval_col: "interval",
                "Repository": "repository",
                "Author": "author",
                "Language": "language",
                "NLOC_Added": "nloc_added",
                "NLOC_Deleted": "nloc_deleted",
                "NLOC": "nloc",
            }
        )

    @staticmethod
    def _serialize_filter_payload(payload: dict[str, object]) -> str:
        """
        Serialize the filter payload for safe embedding into HTML.
        """
        raw = json.dumps(payload, ensure_ascii=False)
        return raw.replace("</", "<\\/")

    def _build_tab_ids(self, repositories: list[str]) -> list[tuple[str, str]]:
        """
        Build stable tab IDs for repositories.
        """
        used_ids: set[str] = set()
        return [(repo, self._safe_id(repo, used_ids)) for repo in repositories]

    def _build_overview_context(self) -> dict[str, object]:
        """
        Build template context for the overview tab.
        """
        meta_items = [
            {"label": "Run directory", "value": self.output_dir.name},
            {"label": "Time interval", "value": self.time_interval},
            {"label": "Repositories analyzed", "value": len(self.repositories)},
        ]
        return {
            "meta_items": meta_items,
            "repositories": self.repositories,
            "totals_table": self._summarize_totals_table(
                self.repository_trend_analysis
            ),
            "language_table": self._summarize_category_table(
                self.language_analysis, "Language"
            ),
            "author_table": self._summarize_category_table(
                self.author_analysis, "Author"
            ),
            "repo_table": self._summarize_category_table(
                self.repository_trend_analysis, "Repository"
            ),
            "repo_trend_chart": self._resolve_chart_html(
                chart_dir=self.output_dir,
                filename=_REPOSITORY_CHART_FILENAME,
                fallback_figure=self._build_trend_figure(
                    self.repository_trend_analysis,
                    category_column="Repository",
                    title="NLOC trend by repository",
                ),
            ),
            "author_contrib_chart": self._resolve_chart_html(
                chart_dir=self.output_dir,
                filename=_AUTHOR_CONTRIBUTION_CHART_FILENAME,
                fallback_figure=self._build_author_contribution_figure(
                    self.author_analysis,
                    title="Author contribution by repository",
                ),
            ),
        }

    def _build_repo_tab_contexts(
        self,
        tab_ids: list[tuple[str, str]],
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> list[dict[str, object]]:
        """
        Build template contexts for repository tabs.
        """
        contexts: list[dict[str, object]] = []
        total_repos = len(tab_ids)
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    label=_LABEL_REPO_TABS,
                    advance=0,
                    total=total_repos,
                    kind="child",
                )
            )
        for repo, tab_id in tab_ids:
            repo_lang = self._subset_by_repo(self.language_analysis, repo)
            repo_author = self._subset_by_repo(self.author_analysis, repo)
            repo_trend = self._subset_by_repo(self.repository_trend_analysis, repo)
            chart_dir = self._repo_chart_dirs.get(repo)
            contexts.append(
                {
                    "id": tab_id,
                    "name": repo,
                    "totals_table": self._summarize_totals_table(repo_trend),
                    "language_table": self._summarize_category_table(
                        repo_lang, "Language"
                    ),
                    "author_table": self._summarize_category_table(
                        repo_author, "Author"
                    ),
                    "exclude_summary": self._exclude_metadata_by_repo.get(repo),
                    "language_chart": self._resolve_chart_html(
                        chart_dir=chart_dir,
                        filename=_LANGUAGE_CHART_FILENAME,
                        fallback_figure=self._build_trend_figure(
                            repo_lang,
                            category_column="Language",
                            title=f"NLOC trend by language - {repo}",
                        ),
                    ),
                    "author_chart": self._resolve_chart_html(
                        chart_dir=chart_dir,
                        filename=_AUTHOR_CHART_FILENAME,
                        fallback_figure=self._build_trend_figure(
                            repo_author,
                            category_column="Author",
                            title=f"NLOC trend by author - {repo}",
                        ),
                    ),
                }
            )
            if progress_callback is not None:
                progress_callback(
                    ProgressEvent(
                        label=_LABEL_REPO_TABS,
                        advance=1,
                        kind="child",
                    )
                )
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(label=_LABEL_REPO_TABS, kind="child", done=True)
            )
        return contexts

    def _subset_by_repo(self, data: pd.DataFrame, repository: str) -> pd.DataFrame:
        """
        Filter analysis data by repository name.
        """
        if data.empty or "Repository" not in data.columns:
            return data.iloc[0:0]
        return data[data["Repository"] == repository]

    def _build_trend_figure(
        self,
        data: pd.DataFrame,
        *,
        category_column: str,
        title: str,
    ) -> object | None:
        """
        Build a trend chart figure using the ChartBuilder.
        """
        if (
            data.empty
            or category_column not in data.columns
            or self.time_interval not in data.columns
        ):
            return None
        trend_data = prepare_trend_data(data, self.time_interval, category_column)
        if trend_data.empty:
            return None
        summary_data = prepare_summary_data(data, self.time_interval)
        chart_builder = ChartBuilder().set_strategy(ChartStrategy.TREND)
        try:
            return chart_builder.build(
                trend_data=trend_data,
                summary_data=summary_data,
                interval=self.time_interval,
                title=title,
            )
        except ValueError:
            return None

    def _build_author_contribution_figure(
        self, data: pd.DataFrame, *, title: str
    ) -> object | None:
        """
        Build an author contribution chart figure.
        """
        if (
            data.empty
            or "Repository" not in data.columns
            or "Author" not in data.columns
        ):
            return None
        summary_data = prepare_author_contribution_data(data)
        if summary_data.empty:
            return None
        chart_builder = ChartBuilder().set_strategy(ChartStrategy.AUTHOR_CONTRIBUTION)
        try:
            return chart_builder.build(
                trend_data=pd.DataFrame(),
                summary_data=summary_data,
                interval="",
                title=title,
            )
        except ValueError:
            return None

    def _render_plotly_figure(self, figure: object | None) -> str:
        """
        Render a Plotly figure as an inline HTML snippet.
        """
        if figure is None:
            return _NO_DATA_MESSAGE
        return pio.to_html(figure, full_html=False, include_plotlyjs=False)

    def _resolve_chart_html(
        self,
        *,
        chart_dir: Path | None,
        filename: str,
        fallback_figure: object | None,
    ) -> str:
        """
        Resolve chart HTML from disk or fall back to rendered figures.
        """
        if chart_dir is not None:
            chart_path = chart_dir / filename
            if chart_path.exists():
                return self._load_chart_html(chart_path)
        return self._render_plotly_figure(fallback_figure)

    def _load_chart_html(self, chart_path: Path) -> str:
        """
        Load Plotly HTML and strip external script includes.
        """
        raw = chart_path.read_text(encoding="utf-8")
        body = raw
        if "<body>" in raw and "</body>" in raw:
            body = raw.split("<body>", 1)[1].split("</body>", 1)[0]
        body = re.sub(r"<script[^>]+src=[^>]+></script>", "", body, flags=re.IGNORECASE)
        return body.strip() or _NO_DATA_MESSAGE

    def _summarize_category_table(
        self,
        analysis: pd.DataFrame,
        category_column: str,
        top_n: int = 10,
    ) -> str:
        """
        Build an HTML table for a summary category.
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
                self._format_number(row["NLOC_Added"]),
                self._format_number(row["NLOC_Deleted"]),
                self._format_number(row["NLOC"]),
            ]
            for _, row in summary.iterrows()
        ]
        return self._build_table(
            headers=["Name", "Added", "Deleted", "NLOC"],
            rows=rows,
            align_right={1, 2, 3},
        )

    def _summarize_totals_table(self, repository_trend_analysis: pd.DataFrame) -> str:
        """
        Build an HTML table for overall totals.
        """
        if repository_trend_analysis.empty:
            return _NO_DATA_MESSAGE
        totals = repository_trend_analysis[["NLOC_Added", "NLOC_Deleted", "NLOC"]].sum()
        rows = [
            [
                self._format_number(totals.get("NLOC_Added", 0)),
                self._format_number(totals.get("NLOC_Deleted", 0)),
                self._format_number(totals.get("NLOC", 0)),
            ]
        ]
        return self._build_table(
            headers=["Added", "Deleted", "NLOC"],
            rows=rows,
            align_right={0, 1, 2},
        )

    def _build_table(
        self,
        *,
        headers: list[str],
        rows: list[list[str]],
        align_right: set[int] | None = None,
    ) -> str:
        """
        Build a basic HTML table with Tabler-style classes.
        """
        if not rows:
            return _NO_DATA_MESSAGE
        align_right = align_right or set()
        header_cells = [
            f"<th class=\"{'text-end' if index in align_right else ''}\">{html.escape(header)}</th>"
            for index, header in enumerate(headers)
        ]
        row_lines = []
        for row in rows:
            cells = []
            for index, cell in enumerate(row):
                align_class = "text-end" if index in align_right else ""
                cells.append(f'<td class="{align_class}">{html.escape(cell)}</td>')
            row_lines.append(f"<tr>{''.join(cells)}</tr>")
        return "\n".join(
            [
                '<table class="table">',
                f"  <thead><tr>{''.join(header_cells)}</tr></thead>",
                f"  <tbody>{''.join(row_lines)}</tbody>",
                "</table>",
            ]
        )

    @staticmethod
    def _to_int(value: object) -> int:
        """
        Convert a value to int safely.
        """
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _format_number(cls, value: object) -> str:
        """
        Format numeric values with a thousands separator.
        """
        return f"{cls._to_int(value):,}"

    @staticmethod
    def _safe_id(value: str, used_ids: set[str]) -> str:
        """
        Build a safe HTML id for tab targets.
        """
        cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip(
            "-"
        )
        cleaned = cleaned or "repo"
        candidate = cleaned
        counter = 2
        while candidate in used_ids:
            candidate = f"{cleaned}-{counter}"
            counter += 1
        used_ids.add(candidate)
        return candidate


def generate_html_report(
    *,
    output_dir: Path,
    charts_root: Path | None,
    time_interval: str,
    language_analysis: pd.DataFrame,
    author_analysis: pd.DataFrame,
    repository_trend_analysis: pd.DataFrame,
    detail_analysis: pd.DataFrame,
    progress_callback: ProgressCallback | None = None,
    exclude_metadata: list[dict[str, object]] | None = None,
) -> None:
    """
    Generate a single HTML report in the run output directory.

    Args:
        output_dir (Path): The output directory for the run.
        charts_root (Path | None): Root directory containing per-repo charts.
        time_interval (str): The time interval label used for aggregation.
        language_analysis (pd.DataFrame): Language analysis data.
        author_analysis (pd.DataFrame): Author analysis data.
        repository_trend_analysis (pd.DataFrame): Repository trend data.
        detail_analysis (pd.DataFrame): Detailed data used for report filters.
        progress_callback (ProgressCallback | None): Optional callback
            invoked after each report generation step.
        exclude_metadata (list[dict[str, object]] | None): Optional per-repository
            exclude template and path decisions to render in repository tabs.
    """
    builder = HtmlReportBuilder(
        output_dir=output_dir,
        charts_root=charts_root,
        time_interval=time_interval,
        language_analysis=language_analysis,
        author_analysis=author_analysis,
        repository_trend_analysis=repository_trend_analysis,
        detail_analysis=detail_analysis,
        exclude_metadata=exclude_metadata,
    )
    builder.generate(progress_callback=progress_callback)
