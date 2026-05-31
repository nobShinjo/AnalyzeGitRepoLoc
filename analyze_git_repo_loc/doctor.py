"""Preflight diagnostics for repository analysis configuration.

Description:
    Provides reusable local and optional remote checks for YAML configuration.
    The doctor command uses these checks directly, and the interactive TUI can
    render the same lightweight issues during final review.

Classes:
    DiagnosticIssue
        Represents one diagnostic finding with severity and message.
    DiagnosticResult
        Collects findings and computes command exit behavior.

Functions:
    run_config_diagnostics
        Validate a configuration file and optionally verify remote providers.
    run_data_diagnostics
        Validate already-built configuration data without reading from disk.
    format_diagnostic_report
        Render diagnostic findings for CLI or TUI output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.remote.remote_catalog import (
    GitHubProviderSettings,
    GitLabProviderSettings,
    RemoteCatalogError,
    RemoteRepositoryRef,
    TuiDefaults,
    TuiProviderSettings,
    TuiSettings,
    fetch_github_branches,
    fetch_gitlab_branches,
    fetch_remote_repositories,
    load_tui_settings,
)
from analyze_git_repo_loc.interactive.tui_auth import (
    build_auth_method_statuses,
    choose_auto_auth_status,
)
from analyze_git_repo_loc.config.yaml_config import load_yaml_data


SECRET_KEY_PARTS = ("token", "password", "secret", "client_id")
VALID_INTERVALS = {"daily", "weekly", "monthly"}


@dataclass(frozen=True)
class DiagnosticIssue:
    """One preflight diagnostic finding."""

    severity: str
    message: str


@dataclass
class DiagnosticResult:
    """Collected preflight diagnostics."""

    issues: list[DiagnosticIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[DiagnosticIssue]:
        """Return all error findings."""

        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[DiagnosticIssue]:
        """Return all warning findings."""

        return [issue for issue in self.issues if issue.severity == "warning"]

    def add(self, severity: str, message: str) -> None:
        """Append a diagnostic finding."""

        self.issues.append(DiagnosticIssue(severity=severity, message=message))

    def extend(self, other: "DiagnosticResult") -> None:
        """Append findings from another result."""

        self.issues.extend(other.issues)

    def exit_code(self, *, strict: bool = False) -> int:
        """Return the recommended process exit code."""

        if self.errors or (strict and self.warnings):
            return 1
        return 0


def run_config_diagnostics(
    config_path: Path,
    *,
    remote: bool = False,
) -> DiagnosticResult:
    """Validate a YAML config file and optionally check remote providers."""

    result = DiagnosticResult()
    try:
        data = load_yaml_data(config_path)
    except ValueError as ex:
        result.add("error", str(ex))
        return result

    result.extend(run_data_diagnostics(data, base_path=config_path.parent, remote=remote))
    return result


def run_data_diagnostics(
    config_data: dict[str, Any],
    *,
    base_path: Path | None = None,
    remote: bool = False,
) -> DiagnosticResult:
    """Validate configuration data that has already been loaded or built."""

    result = DiagnosticResult()
    base_path = base_path or Path.cwd()

    _check_secret_keys(config_data, result)
    settings = _mapping_value(config_data, "settings", result)
    repositories = _repositories_value(config_data, result)
    if settings is not None:
        _check_settings(settings, base_path, result)
    if repositories is not None:
        _check_repositories(repositories, base_path, result)
    _check_interactive(config_data, result, remote=remote)
    return result


def format_diagnostic_report(
    result: DiagnosticResult,
    *,
    title: str | None = None,
    success_message: str | None = None,
) -> str:
    """Render diagnostic findings as human-readable text."""

    title = title or tr("doctor.report_title")
    success_message = success_message or tr("doctor.report_success")
    if not result.issues:
        return f"{title}\n{success_message}"
    lines = [title]
    for issue in result.issues:
        lines.append(f"[{issue.severity.upper()}] {issue.message}")
    return "\n".join(lines)


def _mapping_value(
    data: dict[str, Any],
    key: str,
    result: DiagnosticResult,
) -> dict[str, Any] | None:
    value = data.get(key) or {}
    if not isinstance(value, dict):
        result.add("error", tr("doctor.error.mapping", key=key))
        return None
    return value


def _repositories_value(
    data: dict[str, Any],
    result: DiagnosticResult,
) -> list[Any] | None:
    repositories = data.get("repositories")
    if repositories is None:
        if "interactive" not in data:
            result.add("error", tr("doctor.error.repositories_or_interactive_required"))
        return []
    if not isinstance(repositories, list):
        result.add("error", tr("doctor.error.repositories_list"))
        return None
    if not repositories and "interactive" not in data:
        result.add("error", tr("doctor.error.repositories_non_empty"))
    return repositories


def _check_secret_keys(
    value: Any,
    result: DiagnosticResult,
    *,
    path: str = "",
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            normalized = key_text.lower()
            if any(part in normalized for part in SECRET_KEY_PARTS):
                result.add("error", tr("doctor.error.secret_key", path=child_path))
            _check_secret_keys(child, result, path=child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_secret_keys(child, result, path=f"{path}[{index}]")


def _check_settings(
    settings: dict[str, Any],
    base_path: Path,
    result: DiagnosticResult,
) -> None:
    interval = settings.get("interval")
    if interval is not None and str(interval) not in VALID_INTERVALS:
        result.add("error", tr("doctor.error.interval"))

    since = _parse_date(settings.get("since"), "settings.since", result)
    until = _parse_date(settings.get("until"), "settings.until", result)
    if since and until and since > until:
        result.add("error", tr("doctor.error.date_order"))

    workers = settings.get("workers")
    if workers is not None:
        try:
            if int(workers) < 1:
                result.add("error", tr("doctor.error.workers_min"))
        except (TypeError, ValueError):
            result.add("error", tr("doctor.error.workers_int"))

    output = settings.get("output")
    if output:
        output_parent = _resolve_path(base_path, Path(str(output))).parent
        if not output_parent.exists():
            result.add("warning", tr("doctor.warning.output_parent_missing", path=output_parent))

    for template_file in _as_list(settings.get("exclude_template_files")):
        path = _resolve_path(base_path, Path(str(template_file)))
        if not path.exists():
            result.add("warning", tr("doctor.warning.exclude_template_file_missing", path=path))


def _check_repositories(
    repositories: list[Any],
    base_path: Path,
    result: DiagnosticResult,
) -> None:
    for index, entry in enumerate(repositories):
        repository = {"path": entry} if isinstance(entry, str) else entry
        label = f"repositories[{index}]"
        if not isinstance(repository, dict):
            result.add("error", tr("doctor.error.repository_entry_type", label=label))
            continue
        path_value = repository.get("path")
        if not path_value:
            result.add("error", tr("doctor.error.repository_path_required", label=label))
            continue
        path_text = str(path_value)
        if not _is_git_url(path_text):
            path = _resolve_path(base_path, Path(path_text))
            if not path.exists():
                result.add("warning", tr("doctor.warning.repository_path_missing", path=path))
        include_subpath = repository.get("include_subpath")
        if include_subpath:
            _check_include_subpath(str(include_subpath), label, result)
        for exclude_dir in _as_list(repository.get("exclude_dirs")):
            exclude_path = Path(str(exclude_dir))
            if exclude_path.is_absolute():
                result.add(
                    "warning",
                    tr("doctor.warning.exclude_dir_relative", label=label, path=exclude_dir),
                )


def _check_include_subpath(
    include_subpath: str,
    label: str,
    result: DiagnosticResult,
) -> None:
    path = Path(include_subpath)
    if path.is_absolute():
        result.add("error", tr("doctor.error.include_subpath_relative", label=label))
    if ".." in path.parts:
        result.add("error", tr("doctor.error.include_subpath_traversal", label=label))


def _check_interactive(
    config_data: dict[str, Any],
    result: DiagnosticResult,
    *,
    remote: bool,
) -> None:
    if "interactive" not in config_data:
        if remote:
            result.add("warning", tr("doctor.warning.remote_skipped"))
        return
    settings: Any | None = None
    try:
        settings = load_tui_settings(config_data)
    except RemoteCatalogError as ex:
        result.add("error", str(ex))
        if not remote:
            return
        settings = _recover_remote_settings(config_data)
        if settings is None:
            return
    if remote:
        tokens = _provider_tokens(settings)
        missing_auth = False
        for provider, token in tokens.items():
            if not token:
                missing_auth = True
                result.add(
                    "error",
                    tr("doctor.error.remote_auth_required", provider=provider),
                )
        if missing_auth:
            return
        try:
            refs = fetch_remote_repositories(settings, auth_tokens=tokens)
        except RemoteCatalogError as ex:
            result.add("error", str(ex))
            return
        _check_remote_targets(
            repositories=config_data.get("repositories") or [],
            settings=settings,
            refs=refs,
            tokens=tokens,
            result=result,
        )


def _provider_tokens(settings: Any) -> dict[str, str]:
    tokens: dict[str, str] = {}
    if settings.providers.github.enabled:
        tokens["github"] = _provider_token(
            provider="github",
            base_url=settings.providers.github.api_base_url,
        )
    if settings.providers.gitlab.enabled:
        tokens["gitlab"] = _provider_token(
            provider="gitlab",
            base_url=settings.providers.gitlab.base_url,
        )
    return tokens


def _provider_token(*, provider: str, base_url: str) -> str:
    statuses = build_auth_method_statuses(provider=provider, base_url=base_url)
    status = choose_auto_auth_status(statuses)
    return status.token if status and status.token else ""


def _recover_remote_settings(config_data: dict[str, Any]) -> TuiSettings | None:
    interactive = config_data.get("interactive")
    if not isinstance(interactive, dict):
        return None
    providers = interactive.get("providers")
    if not isinstance(providers, dict):
        return None
    github_raw = providers.get("github")
    gitlab_raw = providers.get("gitlab")
    if not isinstance(github_raw, dict) or not isinstance(gitlab_raw, dict):
        return None
    github = GitHubProviderSettings(
        enabled=bool(github_raw.get("enabled", False)),
        api_base_url=str(github_raw.get("api_base_url") or "https://api.github.com").rstrip("/"),
    )
    gitlab = GitLabProviderSettings(
        enabled=bool(gitlab_raw.get("enabled", False)),
        base_url=str(gitlab_raw.get("base_url") or "https://gitlab.com").rstrip("/"),
    )
    if not github.enabled and not gitlab.enabled:
        return None
    return TuiSettings(
        providers=TuiProviderSettings(github=github, gitlab=gitlab),
        defaults=TuiDefaults(clone_protocol="https"),
    )


def _check_remote_targets(
    *,
    repositories: list[Any],
    settings: Any,
    refs: list[RemoteRepositoryRef],
    tokens: dict[str, str],
    result: DiagnosticResult,
) -> None:
    refs_by_url = {
        _normalize_remote_url(url): ref
        for ref in refs
        for url in (ref.clone_url, ref.ssh_url)
        if url
    }
    for entry in repositories:
        repository = {"path": entry} if isinstance(entry, str) else entry
        if not isinstance(repository, dict):
            continue
        path_value = repository.get("path")
        if not path_value:
            continue
        path_text = str(path_value)
        if not _is_git_url(path_text):
            continue
        ref = refs_by_url.get(_normalize_remote_url(path_text))
        if ref is None:
            result.add("error", tr("doctor.error.remote_repo_missing", path=path_text))
            continue
        branch = repository.get("branch")
        if not branch:
            continue
        try:
            branches = _fetch_remote_branches(ref=ref, settings=settings, tokens=tokens)
        except RemoteCatalogError as ex:
            result.add("error", str(ex))
            continue
        if str(branch) not in branches:
            result.add(
                "error",
                tr(
                    "doctor.error.remote_branch_missing",
                    branch=branch,
                    repository=ref.full_name,
                ),
            )


def _fetch_remote_branches(
    *,
    ref: RemoteRepositoryRef,
    settings: Any,
    tokens: dict[str, str],
) -> list[str]:
    if ref.provider == "github":
        return fetch_github_branches(
            api_base_url=settings.providers.github.api_base_url,
            full_name=ref.full_name,
            token=tokens["github"],
        )
    if ref.provider == "gitlab":
        return fetch_gitlab_branches(
            base_url=settings.providers.gitlab.base_url,
            full_name=ref.full_name,
            token=tokens["gitlab"],
        )
    raise RemoteCatalogError(tr("doctor.error.remote_provider_unsupported", provider=ref.provider))


def _parse_date(
    value: Any,
    name: str,
    result: DiagnosticResult,
) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        result.add("error", tr("doctor.error.date_format", name=name))
        return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _resolve_path(base_path: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return base_path / path


def _is_git_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https", "ssh", "git"}:
        return True
    return value.startswith("git@") and ":" in value


def _normalize_remote_url(value: str) -> str:
    if value.startswith("git@") and ":" in value:
        host, path = value[4:].split(":", 1)
        return f"ssh://{host.lower()}/{path.strip('/').removesuffix('.git')}"
    path = value.strip()
    if path.endswith(".git"):
        path = path[:-4]
    return path.rstrip("/").lower()
