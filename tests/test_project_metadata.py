"""Tests for project metadata and locked dependency expectations.

Description:
    Checks release versions, installation entry points, and dependency floors.

Functions:
    test_pyproject_version_and_dependency_floors_match_release_expectations():
	Validate the release metadata and default development dependencies.
    test_uv_lock_pins_gitpython_to_secure_release():
	Validate the locked project version and patched GitPython release.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from analyze_git_repo_loc import __version__

_EXPECTED_VERSION = "3.3.0"
_EXPECTED_DEPENDENCIES = {
    "pandas": ">=3.1.1",
    "plotly": ">=7.1.0",
    "tqdm": ">=4.70.1",
    "jinja2": ">=3.1.6",
    "PyDriller": ">=2.12",
    "PyYAML": ">=6.0.3",
    "pip-licenses": ">=5.5.5",
    "prompt_toolkit": ">=3.0.53",
    "GitPython": ">=3.2.1",
    "colorama": ">=0.4.6",
}
_EXPECTED_DEV_DEPENDENCIES = {"pytest": ">=9.2.0"}


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
    """The release metadata should match the current minor release plan."""
    data = _load_pyproject_data()
    project = data["project"]
    assert isinstance(project, dict)
    assert project["version"] == _EXPECTED_VERSION
    assert __version__ == _EXPECTED_VERSION
    scripts = project["scripts"]
    assert isinstance(scripts, dict)
    assert scripts["analyze-git-repo-loc"] == "analyze_git_repo_loc.__main__:main"

    dependencies = project["dependencies"]
    assert isinstance(dependencies, list)
    assert _load_dependency_map(dependencies) == _EXPECTED_DEPENDENCIES

    dependency_groups = data["dependency-groups"]
    assert isinstance(dependency_groups, dict)
    dev_dependencies = dependency_groups["dev"]
    assert isinstance(dev_dependencies, list)
    assert _load_dependency_map(dev_dependencies) == _EXPECTED_DEV_DEPENDENCIES

    tool_config = data["tool"]
    assert isinstance(tool_config, dict)
    uv_config = tool_config["uv"]
    assert isinstance(uv_config, dict)
    assert uv_config["default-groups"] == ["dev"]


def test_uv_lock_pins_gitpython_to_secure_release() -> None:
    """The lockfile should resolve GitPython to the patched release line."""
    lock_path = Path(__file__).resolve().parents[1] / "uv.lock"
    lock_data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    packages = {package["name"]: package for package in lock_data["package"]}

    assert packages["gitpython"]["version"] == "3.2.1"
    assert packages["analyze-git-repo-loc"]["version"] == _EXPECTED_VERSION
    assert packages["analyze-git-repo-loc"]["source"] == {"editable": "."}
