"""Excluded path template detection.

Description:
	Provides built-in and user-defined templates for common generated or
	dependency directories. The recommendation API keeps manual and template
	paths separate so callers can preserve warnings for user-entered paths only.

Classes:
	ExcludeTemplate:
		Definition of a project template and its excluded directories.
	DetectedExcludeTemplate:
		A template matched against a repository root.
	ExcludeRecommendation:
		Merged manual and template exclude paths with provenance.

Functions:
	load_exclude_templates:
		Load built-in templates and optional user-defined overrides.
	detect_exclude_templates:
		Detect templates that match a repository root.
	build_exclude_recommendation:
		Build the final exclude list for a repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

ExcludeTemplateMode = Literal["auto", "manual", "off"]


@dataclass(frozen=True)
class ExcludeTemplate:
    """Project template used to infer generated or dependency paths."""

    name: str
    display_name: str
    detect: tuple[str, ...]
    exclude_dirs: tuple[str, ...]
    priority: int = 100
    description: str = ""


@dataclass(frozen=True)
class DetectedExcludeTemplate:
    """A detected exclude template and the patterns that matched it."""

    template: ExcludeTemplate
    matched_patterns: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExcludeRecommendation:
    """Merged exclude paths and their manual/template provenance."""

    paths: list[str]
    manual_paths: list[str]
    template_paths: list[str]
    detected_templates: list[DetectedExcludeTemplate]
    selected_template_names: list[str]
    mode: ExcludeTemplateMode


BUILTIN_EXCLUDE_TEMPLATES: tuple[ExcludeTemplate, ...] = (
    ExcludeTemplate(
        name="unity",
        display_name="Unity Project",
        detect=("ProjectSettings/ProjectVersion.txt", "Assets", "Packages/manifest.json"),
        exclude_dirs=("Library", "Temp", "Obj", "Build", "Builds", "Logs", "UserSettings"),
        priority=10,
        description="Unity generated assets, build output, and editor state.",
    ),
    ExcludeTemplate(
        name="dotnet",
        display_name=".NET Project",
        detect=("*.sln", "*.csproj", "*.fsproj", "*.vbproj"),
        exclude_dirs=("bin", "obj", ".vs", "TestResults"),
        priority=20,
        description=".NET build output and IDE state.",
    ),
    ExcludeTemplate(
        name="python",
        display_name="Python Project",
        detect=("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile", ".venv"),
        exclude_dirs=(
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
        ),
        priority=30,
        description="Python virtual environments, caches, and packaging output.",
    ),
    ExcludeTemplate(
        name="node",
        display_name="Node.js Project",
        detect=("package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json", "node_modules"),
        exclude_dirs=("node_modules", ".next", ".nuxt", "dist", "build", "coverage"),
        priority=40,
        description="JavaScript dependencies and common frontend build output.",
    ),
    ExcludeTemplate(
        name="java",
        display_name="Java Project",
        detect=("pom.xml", "build.gradle", "build.gradle.kts", ".gradle"),
        exclude_dirs=("target", "build", ".gradle", "out"),
        priority=50,
        description="Maven/Gradle build output and caches.",
    ),
    ExcludeTemplate(
        name="rust",
        display_name="Rust Project",
        detect=("Cargo.toml",),
        exclude_dirs=("target",),
        priority=60,
        description="Cargo build output.",
    ),
    ExcludeTemplate(
        name="go",
        display_name="Go Project",
        detect=("go.mod",),
        exclude_dirs=("vendor",),
        priority=70,
        description="Vendored Go dependencies.",
    ),
)


def load_exclude_templates(template_files: list[str] | None = None) -> list[ExcludeTemplate]:
    """Load built-in templates and optional user-defined overrides."""
    templates = {template.name: template for template in BUILTIN_EXCLUDE_TEMPLATES}
    for template_file in template_files or []:
        path = Path(template_file).expanduser()
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw_templates = data.get("templates", data) if isinstance(data, dict) else data
        if not isinstance(raw_templates, list):
            raise ValueError(f"Exclude template file must contain a template list: {path}")
        for raw_template in raw_templates:
            template = _parse_user_template(raw_template, path)
            templates[template.name] = template
    return sorted(templates.values(), key=lambda template: (template.priority, template.name))


def detect_exclude_templates(
    repo_root: Path,
    *,
    templates: list[ExcludeTemplate] | None = None,
) -> list[DetectedExcludeTemplate]:
    """Detect exclude templates that match a repository root."""
    if not repo_root.exists() or not repo_root.is_dir():
        return []
    template_defs = templates if templates is not None else load_exclude_templates()
    detected: list[DetectedExcludeTemplate] = []
    for template in template_defs:
        matches = tuple(pattern for pattern in template.detect if _matches_pattern(repo_root, pattern))
        if matches:
            detected.append(DetectedExcludeTemplate(template=template, matched_patterns=matches))
    return sorted(detected, key=lambda item: (item.template.priority, item.template.name))


def build_exclude_recommendation(
    repo_root: Path,
    *,
    manual_excludes: list[str] | None = None,
    selected_template_names: list[str] | None = None,
    mode: ExcludeTemplateMode = "auto",
    templates: list[ExcludeTemplate] | None = None,
) -> ExcludeRecommendation:
    """Build merged exclude paths for a repository."""
    normalized_mode = normalize_exclude_template_mode(mode)
    manual_paths = _deduplicate(manual_excludes or [])
    if normalized_mode == "off":
        return ExcludeRecommendation(
            paths=[],
            manual_paths=manual_paths,
            template_paths=[],
            detected_templates=[],
            selected_template_names=[],
            mode=normalized_mode,
        )
    if normalized_mode == "manual":
        return ExcludeRecommendation(
            paths=manual_paths,
            manual_paths=manual_paths,
            template_paths=[],
            detected_templates=[],
            selected_template_names=[],
            mode=normalized_mode,
        )

    template_defs = templates if templates is not None else load_exclude_templates()
    detected = detect_exclude_templates(repo_root, templates=template_defs)
    detected_by_name = {item.template.name: item for item in detected}
    templates_by_name = {template.name: template for template in template_defs}
    if selected_template_names is None:
        selected_names = [item.template.name for item in detected]
    else:
        selected_names = [
            name for name in _deduplicate(selected_template_names) if name in templates_by_name
        ]
    template_paths: list[str] = []
    for name in selected_names:
        template = templates_by_name[name]
        template_paths.extend(template.exclude_dirs)
    paths = _deduplicate([*manual_paths, *template_paths])
    selected_detected = [
        detected_by_name[name] for name in selected_names if name in detected_by_name
    ]
    return ExcludeRecommendation(
        paths=paths,
        manual_paths=manual_paths,
        template_paths=_deduplicate(template_paths),
        detected_templates=selected_detected,
        selected_template_names=selected_names,
        mode=normalized_mode,
    )


def normalize_exclude_template_mode(value: object) -> ExcludeTemplateMode:
    """Normalize and validate an exclude template mode value."""
    mode = str(value or "auto").strip().casefold()
    if mode not in {"auto", "manual", "off"}:
        raise ValueError("exclude_template_mode must be auto, manual, or off.")
    return mode  # type: ignore[return-value]


def _matches_pattern(repo_root: Path, pattern: str) -> bool:
    candidate = repo_root / pattern
    if any(character in pattern for character in "*?[]"):
        return any(repo_root.glob(pattern))
    return candidate.exists()


def _parse_user_template(raw_template: Any, path: Path) -> ExcludeTemplate:
    if not isinstance(raw_template, dict):
        raise ValueError(f"Exclude template entries must be mappings: {path}")
    name = str(raw_template.get("name") or "").strip()
    if not name:
        raise ValueError(f"Exclude template requires a name: {path}")
    detect = _string_tuple(raw_template.get("detect"))
    exclude_dirs = _string_tuple(raw_template.get("exclude_dirs"))
    if not detect or not exclude_dirs:
        raise ValueError(f"Exclude template requires detect and exclude_dirs: {name}")
    return ExcludeTemplate(
        name=name,
        display_name=str(raw_template.get("display_name") or name),
        detect=detect,
        exclude_dirs=exclude_dirs,
        priority=int(raw_template.get("priority") or 100),
        description=str(raw_template.get("description") or ""),
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    raise ValueError("Template values must be strings or lists of strings.")


def _deduplicate(values: list[str] | tuple[str, ...]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
