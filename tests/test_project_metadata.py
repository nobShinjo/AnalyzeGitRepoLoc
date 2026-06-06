"""Tests for project metadata and locked dependency expectations."""

from __future__ import annotations

import tomllib
from pathlib import Path


_EXPECTED_VERSION = "3.1.0"
_EXPECTED_DEPENDENCIES = {
    "pandas": ">=3.0.3",
    "plotly": ">=6.7.0",
    "tqdm": ">=4.67.3",
    "jinja2": ">=3.1.6",
    "PyDriller": ">=2.9",
    "PyYAML": ">=6.0.3",
    "pip-licenses": ">=5.5.5",
    "prompt_toolkit": ">=3.0.52",
    "GitPython": ">=3.1.50",
    "colorama": ">=0.4.6",
}
_EXPECTED_DEV_DEPENDENCIES = {"pytest": ">=9.0.3"}


def _load_pyproject_data() -> dict[str, object]:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    return tomllib.loads(pyproject_path.read_text(encoding="utf-8"))


def _load_dependency_map(requirements: list[str]) -> dict[str, str]:
    dependency_map: dict[str, str] = {}
    for requirement in requirements:
        name, specifier = requirement.split(">=", maxsplit=1)
        dependency_map[name] = f">={specifier}"
    return dependency_map


def test_pyproject_version_and_dependency_floors_match_release_expectations() -> None:
    """The release metadata should match the 3.1.0 dependency refresh plan."""
    data = _load_pyproject_data()
    project = data["project"]
    assert isinstance(project, dict)
    assert project["version"] == _EXPECTED_VERSION

    dependencies = project["dependencies"]
    assert isinstance(dependencies, list)
    assert _load_dependency_map(dependencies) == _EXPECTED_DEPENDENCIES

    dependency_groups = data["dependency-groups"]
    assert isinstance(dependency_groups, dict)
    dev_dependencies = dependency_groups["dev"]
    assert isinstance(dev_dependencies, list)
    assert _load_dependency_map(dev_dependencies) == _EXPECTED_DEV_DEPENDENCIES


def test_uv_lock_pins_gitpython_to_secure_release() -> None:
    """The lockfile should resolve GitPython to the patched release line."""
    lock_path = Path(__file__).resolve().parents[1] / "uv.lock"
    lock_text = lock_path.read_text(encoding="utf-8")

    assert 'name = "gitpython"\nversion = "3.1.50"' in lock_text
