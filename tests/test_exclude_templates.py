"""Tests for excluded path template recommendations."""

from __future__ import annotations

from pathlib import Path

from analyze_git_repo_loc.exclude_templates import (
    ExcludeTemplate,
    build_exclude_recommendation,
    detect_exclude_templates,
    load_exclude_templates,
)


def test_detects_python_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

    detected = detect_exclude_templates(tmp_path)

    assert [item.template.name for item in detected] == ["python"]


def test_detects_unity_before_dotnet_when_both_match(tmp_path: Path) -> None:
    (tmp_path / "ProjectSettings").mkdir()
    (tmp_path / "ProjectSettings" / "ProjectVersion.txt").write_text(
        "m_EditorVersion: 6000.0\n",
        encoding="utf-8",
    )
    (tmp_path / "Game.csproj").write_text("<Project />\n", encoding="utf-8")

    detected = detect_exclude_templates(tmp_path)

    assert [item.template.name for item in detected][:2] == ["unity", "dotnet"]


def test_auto_recommendation_merges_manual_and_template_paths(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")

    recommendation = build_exclude_recommendation(
        tmp_path,
        manual_excludes=["custom", "node_modules"],
        mode="auto",
    )

    assert recommendation.manual_paths == ["custom", "node_modules"]
    assert "node_modules" in recommendation.template_paths
    assert recommendation.paths.count("node_modules") == 1
    assert "coverage" in recommendation.paths


def test_manual_mode_ignores_detected_template_paths(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'demo'\n", encoding="utf-8")

    recommendation = build_exclude_recommendation(
        tmp_path,
        manual_excludes=["manual-only"],
        mode="manual",
    )

    assert recommendation.paths == ["manual-only"]
    assert recommendation.template_paths == []


def test_off_mode_disables_all_excludes(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module example.com/demo\n", encoding="utf-8")

    recommendation = build_exclude_recommendation(
        tmp_path,
        manual_excludes=["vendor"],
        mode="off",
    )

    assert recommendation.paths == []
    assert recommendation.manual_paths == ["vendor"]


def test_user_template_overrides_builtin(tmp_path: Path) -> None:
    template_file = tmp_path / "templates.yml"
    template_file.write_text(
        "\n".join(
            [
                "templates:",
                "- name: python",
                "  display_name: Custom Python",
                "  detect: pyproject.toml",
                "  exclude_dirs:",
                "  - custom-cache",
                "  priority: 5",
            ]
        ),
        encoding="utf-8",
    )

    templates = load_exclude_templates([str(template_file)])
    python_template = next(template for template in templates if template.name == "python")

    assert isinstance(python_template, ExcludeTemplate)
    assert python_template.display_name == "Custom Python"
    assert python_template.exclude_dirs == ("custom-cache",)
