"""Tests for terminal-independent TUI wizard state and flow behavior."""

from __future__ import annotations

# pylint: disable=missing-function-docstring

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from analyze_git_repo_loc import utils
from analyze_git_repo_loc.__main__ import _format_output_summary
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.interactive import tui_wizard
from analyze_git_repo_loc.interactive.tui_selector import RepositorySelectionResult
from analyze_git_repo_loc.interactive.tui_wizard import (
    ProviderTarget,
    SelectedRepositoryConfig,
    TuiWizardState,
    apply_branch_selection,
    apply_repository_overrides,
    apply_wizard_state,
    build_lightweight_recommendations,
    build_provider_candidates,
    choose_auto_provider_targets,
    format_compact_list,
    load_quick_defaults,
    normalize_final_action,
    render_final_review,
    selected_targets_to_settings,
    save_wizard_config,
    wizard_state_to_config,
)
from analyze_git_repo_loc.remote.remote_catalog import (
    RemoteCatalogError,
    RemoteRepositoryRef,
    load_tui_settings,
)


class TuiWizardStateTests(unittest.TestCase):
    """Terminal-independent full wizard state tests."""

    def test_load_quick_defaults_reads_non_secret_interactive_presets(self) -> None:
        defaults = load_quick_defaults(
            {
                "interactive": {
                    "quick_defaults": {
                        "interval": "weekly",
                        "lang": ["Python", "Markdown"],
                        "exclude_dirs": "node_modules,.venv",
                        "cache_policy": "update",
                        "no_plot_show": True,
                    }
                }
            }
        )

        self.assertEqual(defaults.interval, "weekly")
        self.assertEqual(defaults.lang, ["Python", "Markdown"])
        self.assertEqual(defaults.exclude_dirs, ["node_modules", ".venv"])
        self.assertEqual(defaults.cache_policy, "update")
        self.assertTrue(defaults.no_plot_show)

    def test_quick_run_skips_full_edit_prompts(self) -> None:
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[],
            selected_repositories=[],
        )

        with patch(
            "analyze_git_repo_loc.interactive.tui_wizard._prompt_final_action",
            return_value="run",
        ):
            with patch(
                "analyze_git_repo_loc.interactive.tui_wizard._prompt_branch_selection"
            ) as branch:
                with patch(
                    "analyze_git_repo_loc.interactive.tui_wizard._prompt_analysis_scope"
                ) as scope:
                    with patch(
                        "analyze_git_repo_loc.interactive.tui_wizard._prompt_path_rules"
                    ) as path:
                        with patch(
                            "analyze_git_repo_loc.interactive.tui_wizard."
                            "_prompt_output_cache_display"
                        ) as output:
                            # pylint: disable-next=protected-access
                            action = tui_wizard._run_wizard_steps(state)

        self.assertEqual(action, "run")
        branch.assert_not_called()
        scope.assert_not_called()
        path.assert_not_called()
        output.assert_not_called()

    def test_run_tui_wizard_applies_selector_branch_selection(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        args = argparse.Namespace(
            output=Path("out"),
            since=None,
            until=None,
            interval="monthly",
            author_name=None,
            lang=None,
            exclude_dirs=None,
            workers=1,
            clear_cache=False,
            no_plot_show=True,
            config=Path("config.yml"),
        )
        config = {"interactive": {"providers": {"github": {"enabled": True}}}}

        with patch(
            "analyze_git_repo_loc.interactive.tui_wizard.choose_auto_provider_targets",
            return_value=[
                ProviderTarget("github", "github", "GitHub", "https://api.github.com")
            ],
        ):
            with patch(
                "analyze_git_repo_loc.interactive.tui_wizard._authenticate_provider_targets",
                return_value=({"github": "token"}, {"github": "env"}),
            ):
                with patch(
                    "analyze_git_repo_loc.interactive.tui_wizard._fetch_repository_catalog",
                    return_value=[ref],
                ):
                    with patch(
                        "analyze_git_repo_loc.interactive.tui_wizard.run_repository_selector",
                        return_value=RepositorySelectionResult(
                            selected_refs=[ref],
                            selected_branches={"org/alpha": "develop"},
                        ),
                    ) as selector:
                        with patch(
                            "analyze_git_repo_loc.interactive.tui_wizard._prompt_branch_selection"
                        ) as branch:
                            with patch(
                                "analyze_git_repo_loc.interactive.tui_wizard._run_wizard_steps",
                                return_value="run",
                            ):
                                result = tui_wizard.run_tui_wizard(args, config)

        selector.assert_called_once()
        self.assertIn("branch_loader", selector.call_args.kwargs)
        branch.assert_not_called()
        self.assertEqual(result.repo_paths[0][1], "develop")

    def test_run_tui_wizard_reopens_repository_selector_from_final_actions(self) -> None:
        alpha = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        beta = RemoteRepositoryRef(
            "github",
            "beta",
            "org/beta",
            "https://github.com/org/beta.git",
            "",
            "https://github.com/org/beta",
            "develop",
        )
        args = argparse.Namespace(
            output=Path("out"),
            since=None,
            until=None,
            interval="monthly",
            author_name=None,
            lang=None,
            exclude_dirs=None,
            workers=None,
            clear_cache=False,
            no_plot_show=True,
            config=Path("config.yml"),
        )
        config = {"interactive": {"providers": {"github": {"enabled": True}}}}

        with patch(
            "analyze_git_repo_loc.interactive.tui_wizard.choose_auto_provider_targets",
            return_value=[
                ProviderTarget("github", "github", "GitHub", "https://api.github.com")
            ],
        ):
            with patch(
                "analyze_git_repo_loc.interactive.tui_wizard._authenticate_provider_targets",
                return_value=({"github": "token"}, {"github": "env"}),
            ):
                with patch(
                    "analyze_git_repo_loc.interactive.tui_wizard._fetch_repository_catalog",
                    return_value=[alpha, beta],
                ):
                    with patch(
                        "analyze_git_repo_loc.interactive.tui_wizard.run_repository_selector",
                        side_effect=[
                            RepositorySelectionResult(
                                selected_refs=[alpha],
                                selected_branches={"org/alpha": "main"},
                            ),
                            RepositorySelectionResult(
                                selected_refs=[beta],
                                selected_branches={"org/beta": "release"},
                            ),
                        ],
                    ) as selector:
                        with patch(
                            "analyze_git_repo_loc.interactive.tui_wizard._run_wizard_steps",
                            side_effect=["select", "run"],
                        ):
                            result = tui_wizard.run_tui_wizard(args, config)

        self.assertEqual(selector.call_count, 2)
        self.assertEqual(
            selector.call_args_list[1].kwargs["initial_selected_refs"],
            [alpha],
        )
        self.assertEqual(
            selector.call_args_list[1].kwargs["initial_selected_branches"],
            {"org/alpha": "main"},
        )
        self.assertEqual(result.repo_paths[0][0], "https://github.com/org/beta.git")
        self.assertEqual(result.repo_paths[0][1], "release")

    def test_run_tui_wizard_preselects_configured_repository_and_branch(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        args = argparse.Namespace(
            output=Path("out"),
            since=None,
            until=None,
            interval="monthly",
            author_name=None,
            lang=None,
            exclude_dirs=None,
            workers=1,
            clear_cache=False,
            no_plot_show=True,
            config=Path("config.yml"),
        )
        config = {
            "interactive": {"providers": {"github": {"enabled": True}}},
            "repositories": [
                {
                    "path": "https://github.com/org/alpha.git",
                    "branch": "release",
                }
            ],
        }

        with patch(
            "analyze_git_repo_loc.interactive.tui_wizard.choose_auto_provider_targets",
            return_value=[
                ProviderTarget("github", "github", "GitHub", "https://api.github.com")
            ],
        ):
            with patch(
                "analyze_git_repo_loc.interactive.tui_wizard._authenticate_provider_targets",
                return_value=({"github": "token"}, {"github": "env"}),
            ):
                with patch(
                    "analyze_git_repo_loc.interactive.tui_wizard._fetch_repository_catalog",
                    return_value=[ref],
                ):
                    with patch(
                        "analyze_git_repo_loc.interactive.tui_wizard.run_repository_selector",
                        return_value=RepositorySelectionResult(
                            selected_refs=[ref],
                            selected_branches={"org/alpha": "release"},
                        ),
                    ) as selector:
                        with patch(
                            "analyze_git_repo_loc.interactive.tui_wizard._run_wizard_steps",
                            return_value="run",
                        ):
                            tui_wizard.run_tui_wizard(args, config)

        self.assertEqual(selector.call_args.kwargs["initial_selected_refs"], [ref])
        self.assertEqual(
            selector.call_args.kwargs["initial_selected_branches"],
            {"org/alpha": "release"},
        )

    def test_run_tui_wizard_preserves_repository_overrides_from_config(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        args = argparse.Namespace(
            output=Path("out"),
            since=None,
            until=None,
            interval="monthly",
            author_name=None,
            lang=None,
            exclude_dirs=None,
            workers=1,
            clear_cache=False,
            no_plot_show=True,
            config=Path("config.yml"),
        )
        config = {
            "interactive": {"providers": {"github": {"enabled": True}}},
            "repositories": [
                {
                    "path": "https://github.com/org/alpha.git",
                    "branch": "release",
                    "include_subpath": "src/app",
                    "exclude_dirs": ["generated"],
                    "exclude_template_mode": "manual",
                    "exclude_template_names": ["python"],
                }
            ],
        }

        with patch(
            "analyze_git_repo_loc.interactive.tui_wizard.choose_auto_provider_targets",
            return_value=[
                ProviderTarget("github", "github", "GitHub", "https://api.github.com")
            ],
        ):
            with patch(
                "analyze_git_repo_loc.interactive.tui_wizard._authenticate_provider_targets",
                return_value=({"github": "token"}, {"github": "env"}),
            ):
                with patch(
                    "analyze_git_repo_loc.interactive.tui_wizard._fetch_repository_catalog",
                    return_value=[ref],
                ):
                    with patch(
                        "analyze_git_repo_loc.interactive.tui_wizard.run_repository_selector",
                        return_value=RepositorySelectionResult(
                            selected_refs=[ref],
                            selected_branches={},
                        ),
                    ):
                        with patch(
                            "analyze_git_repo_loc.interactive.tui_wizard._run_wizard_steps",
                            return_value="run",
                        ):
                            result = tui_wizard.run_tui_wizard(args, config)

        self.assertEqual(
            result.repo_paths,
            [
                (
                    "https://github.com/org/alpha.git",
                    "release",
                    ["generated"],
                    "src/app",
                    "manual",
                    ["python"],
                )
            ],
        )

    def test_run_tui_wizard_preserves_repository_overrides_for_mixed_providers(self) -> None:
        github_ref = RemoteRepositoryRef(
            "github",
            "core",
            "acme/core",
            "https://github.com/acme/core.git",
            "",
            "https://github.com/acme/core",
            "main",
        )
        gitlab_ref = RemoteRepositoryRef(
            "gitlab",
            "core",
            "acme/core",
            "https://gitlab.example.com/acme/core.git",
            "",
            "https://gitlab.example.com/acme/core",
            "main",
        )
        args = argparse.Namespace(
            output=Path("out"),
            since=None,
            until=None,
            interval="monthly",
            author_name=None,
            lang=None,
            exclude_dirs=None,
            workers=1,
            clear_cache=False,
            no_plot_show=True,
            config=Path("config.yml"),
        )
        config = {
            "interactive": {
                "providers": {
                    "github": {"enabled": True},
                    "gitlab": {
                        "enabled": True,
                        "base_url": "https://gitlab.example.com",
                    },
                }
            },
            "repositories": [
                {
                    "path": "https://github.com/acme/core.git",
                    "branch": "release",
                    "include_subpath": "src/github",
                },
                {
                    "path": "https://gitlab.example.com/acme/core.git",
                    "branch": "develop",
                    "include_subpath": "src/gitlab",
                },
            ],
        }

        with patch(
            "analyze_git_repo_loc.interactive.tui_wizard.choose_auto_provider_targets",
            return_value=[
                ProviderTarget("github", "github", "GitHub", "https://api.github.com"),
                ProviderTarget(
                    "gitlab:https://gitlab.example.com",
                    "gitlab",
                    "GitLab",
                    "https://gitlab.example.com",
                ),
            ],
        ):
            with patch(
                "analyze_git_repo_loc.interactive.tui_wizard._authenticate_provider_targets",
                return_value=(
                    {
                        "github": "gh-token",
                        "gitlab:https://gitlab.example.com": "gl-token",
                    },
                    {
                        "github": "env",
                        "gitlab:https://gitlab.example.com": "env",
                    },
                ),
            ):
                with patch(
                    "analyze_git_repo_loc.interactive.tui_wizard._fetch_repository_catalog",
                    return_value=[github_ref, gitlab_ref],
                ):
                    with patch(
                        "analyze_git_repo_loc.interactive.tui_wizard.run_repository_selector",
                        return_value=RepositorySelectionResult(
                            selected_refs=[github_ref, gitlab_ref],
                            selected_branches={},
                        ),
                    ):
                        with patch(
                            "analyze_git_repo_loc.interactive.tui_wizard._run_wizard_steps",
                            return_value="run",
                        ):
                            result = tui_wizard.run_tui_wizard(args, config)

        self.assertEqual(result.repo_paths[0][1], "release")
        self.assertEqual(result.repo_paths[0][3], "src/github")
        self.assertEqual(result.repo_paths[1][1], "develop")
        self.assertEqual(result.repo_paths[1][3], "src/gitlab")

    def test_lightweight_recommendations_scan_only_existing_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "out"
            cached_repo = output / ".cache" / "remote-repos" / "alpha-123"
            cached_repo.mkdir(parents=True)
            (cached_repo / ".git").mkdir()
            (cached_repo / "src").mkdir()
            (cached_repo / "src" / "app.py").write_text(
                "print('hi')",
                encoding="utf-8",
            )
            (cached_repo / "README.md").write_text("# hi", encoding="utf-8")
            (cached_repo / "node_modules").mkdir()
            (cached_repo / "node_modules" / "ignored.js").write_text(
                "x",
                encoding="utf-8",
            )

            ref = RemoteRepositoryRef(
                "github",
                "alpha",
                "org/alpha",
                "https://github.com/org/alpha.git",
                "",
                "https://github.com/org/alpha",
                "main",
            )
            state = TuiWizardState(
                provider_targets=[],
                auth_tokens={},
                repository_catalog=[ref],
                selected_repositories=[
                    SelectedRepositoryConfig(
                        ref=ref,
                        branch="main",
                        cache_status="cached",
                    )
                ],
                output=output,
            )

            with patch(
                "analyze_git_repo_loc.interactive.tui_wizard.determine_cache_path",
                return_value=cached_repo,
            ):
                recommendations = build_lightweight_recommendations(state)

        self.assertEqual(recommendations.languages[:2], ["Markdown", "Python"])
        self.assertIn("node_modules", recommendations.exclude_dirs)
        self.assertEqual(recommendations.language_source, "existing cache")

    def test_repo_progress_bars_accept_include_subpath_entries(self) -> None:
        progress = Mock(pos=0)
        progress_bar = Mock()

        with patch("analyze_git_repo_loc.utils.tqdm", return_value=progress_bar):
            # pylint: disable-next=protected-access
            repo_bars, repo_labels = utils._build_repo_progress_bars(
                [("https://github.com/org/alpha.git", "main", [], "src")],
                progress=progress,
                label_width=20,
            )

        self.assertEqual(repo_bars, {0: progress_bar})
        self.assertEqual(repo_labels, {0: "alpha"})

    def test_provider_candidates_include_github_gitlab_dotcom_and_self_hosted(
        self,
    ) -> None:
        settings = load_tui_settings(
            {
                "interactive": {
                    "providers": {
                        "github": {"enabled": True},
                        "gitlab": {
                            "enabled": True,
                            "base_url": "https://gitlab.example.com",
                        },
                    }
                }
            }
        )

        candidates = build_provider_candidates(settings)

        self.assertEqual(
            [(candidate.key, candidate.label) for candidate in candidates],
            [
                ("github", "GitHub"),
                ("gitlab.com", "GitLab.com"),
                ("gitlab.self_hosted", "Self-hosted GitLab"),
            ],
        )
        self.assertEqual(candidates[2].base_url, "https://gitlab.example.com")

    def test_choose_auto_provider_targets_returns_single_enabled_provider(self) -> None:
        settings = load_tui_settings(
            {"interactive": {"providers": {"github": {"enabled": True}}}}
        )

        targets = choose_auto_provider_targets(settings)

        self.assertIsNotNone(targets)
        self.assertEqual([target.key for target in targets or []], ["github"])

    def test_choose_auto_provider_targets_returns_none_for_multiple_providers(
        self,
    ) -> None:
        settings = load_tui_settings(
            {
                "interactive": {
                    "providers": {
                        "github": {"enabled": True},
                        "gitlab": {"enabled": True},
                    }
                }
            }
        )

        self.assertIsNone(choose_auto_provider_targets(settings))

    def test_selected_provider_targets_build_runtime_settings(self) -> None:
        settings = selected_targets_to_settings(
            [
                ProviderTarget(
                    key="github",
                    provider="github",
                    label="GitHub",
                    base_url="https://api.github.com",
                ),
                ProviderTarget(
                    key="gitlab.self_hosted",
                    provider="gitlab",
                    label="Self-hosted GitLab",
                    base_url="https://gitlab.example.com",
                ),
            ],
            clone_protocol="ssh",
        )

        self.assertTrue(settings.providers.github.enabled)
        self.assertTrue(settings.providers.gitlab.enabled)
        self.assertEqual(
            settings.providers.gitlab.base_url,
            "https://gitlab.example.com",
        )
        self.assertEqual(settings.defaults.clone_protocol, "ssh")

    def test_apply_wizard_state_updates_args_for_existing_pipeline(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "git@github.com:org/alpha.git",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={"github": "secret"},
            repository_catalog=[ref],
            selected_repositories=[
                SelectedRepositoryConfig(
                    ref=ref,
                    branch="develop",
                    include_subpath="src",
                    exclude_dirs=["generated"],
                )
            ],
            clone_protocol="ssh",
            interval="weekly",
            lang=["Python"],
            author_name=["Nob"],
            workers=2,
            global_exclude_dirs=["vendor"],
            output=Path("out"),
            clear_cache=True,
            no_plot_show=True,
        )
        args = argparse.Namespace()

        apply_wizard_state(args, state)

        self.assertEqual(
            args.repo_paths,
            [
                (
                    "git@github.com:org/alpha.git",
                    "develop",
                    ["vendor", "generated"],
                    "src",
                    None,
                    None,
                )
            ],
        )
        self.assertEqual(args.interval, "weekly")
        self.assertEqual(args.lang, ["Python"])
        self.assertEqual(args.author_name, ["Nob"])
        self.assertEqual(args.workers, 2)
        self.assertIsNone(args.exclude_dirs)
        self.assertTrue(args.clear_cache)
        self.assertTrue(args.no_plot_show)

    def test_apply_wizard_state_keeps_missing_template_ready_excludes(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[ref],
            selected_repositories=[
                SelectedRepositoryConfig(
                    ref=ref,
                    branch="main",
                    cache_status="cached",
                )
            ],
            global_exclude_dirs=["node_modules", ".venv"],
            output=Path("out"),
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            cached_repo = Path(tmp_dir) / "cache" / "alpha"
            (cached_repo / "node_modules").mkdir(parents=True)
            with patch(
                "analyze_git_repo_loc.interactive.tui_wizard.determine_cache_path",
                return_value=cached_repo,
            ):
                args = apply_wizard_state(argparse.Namespace(), state)

        self.assertEqual(args.repo_paths[0][2], ["node_modules", ".venv"])

    def test_include_subpath_rejects_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "repo"
            root.mkdir()

            with self.assertRaisesRegex(ValueError, "repository-root-relative"):
                # pylint: disable-next=protected-access
                utils._apply_include_subpath(root, root / "outside")

    def test_include_subpath_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "repo"
            root.mkdir()

            with self.assertRaisesRegex(ValueError, "within repository root"):
                # pylint: disable-next=protected-access
                utils._apply_include_subpath(root, "../outside")

    def test_format_compact_list_limits_noisy_recommendations(self) -> None:
        formatted = format_compact_list(
            ["Markdown", "Python", "YAML", "JSON", "C#", "JavaScript"],
            limit=3,
        )

        self.assertEqual(formatted, "Markdown, Python, YAML (+3 more)")

    def test_branch_and_repository_overrides_support_bulk_then_individual(
        self,
    ) -> None:
        ref = RemoteRepositoryRef(
            "gitlab",
            "beta",
            "team/beta",
            "https://gitlab.com/team/beta.git",
            "",
            "https://gitlab.com/team/beta",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[ref],
            selected_repositories=[SelectedRepositoryConfig(ref=ref, branch="main")],
        )

        apply_branch_selection(state, "develop")
        apply_repository_overrides(
            state,
            {
                "team/beta": {
                    "branch": "release",
                    "include_subpath": "packages/api",
                    "exclude_dirs": "dist,.cache",
                }
            },
        )

        repository = state.selected_repositories[0]
        self.assertEqual(repository.branch, "release")
        self.assertEqual(repository.include_subpath, "packages/api")
        self.assertEqual(repository.exclude_dirs, ["dist", ".cache"])

    def test_repository_overrides_distinguish_same_full_name_across_providers(
        self,
    ) -> None:
        github_ref = RemoteRepositoryRef(
            "github",
            "core",
            "acme/core",
            "https://github.com/acme/core.git",
            "git@github.com:acme/core.git",
            "https://github.com/acme/core",
            "main",
        )
        gitlab_ref = RemoteRepositoryRef(
            "gitlab",
            "core",
            "acme/core",
            "https://gitlab.example.com/acme/core.git",
            "git@gitlab.example.com:acme/core.git",
            "https://gitlab.example.com/acme/core",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[github_ref, gitlab_ref],
            selected_repositories=[
                SelectedRepositoryConfig(ref=github_ref, branch="main"),
                SelectedRepositoryConfig(ref=gitlab_ref, branch="main"),
            ],
        )

        apply_repository_overrides(
            state,
            {
                "github.com/acme/core": {
                    "branch": "release",
                    "include_subpath": "src/github",
                },
                "gitlab.example.com/acme/core": {
                    "branch": "develop",
                    "include_subpath": "src/gitlab",
                },
            },
        )

        self.assertEqual(state.selected_repositories[0].branch, "release")
        self.assertEqual(
            state.selected_repositories[0].include_subpath,
            "src/github",
        )
        self.assertEqual(state.selected_repositories[1].branch, "develop")
        self.assertEqual(
            state.selected_repositories[1].include_subpath,
            "src/gitlab",
        )

    def test_config_export_omits_auth_tokens(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={"github": "secret"},
            repository_catalog=[ref],
            selected_repositories=[SelectedRepositoryConfig(ref=ref, branch="main")],
            output=Path("out"),
        )

        exported = wizard_state_to_config(state)
        rendered = str(exported)

        self.assertNotIn("secret", rendered)
        self.assertEqual(
            exported["repositories"][0]["path"],
            "https://github.com/org/alpha.git",
        )
        self.assertTrue(exported["settings"]["no_plot_show"])
        self.assertEqual(
            exported["interactive"]["quick_defaults"]["cache_policy"],
            "use",
        )
        self.assertNotIn("tui", exported)
        self.assertNotIn("auth_tokens", rendered)

    def test_save_wizard_config_preserves_commented_repository_candidates(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[ref],
            selected_repositories=[SelectedRepositoryConfig(ref=ref, branch="main")],
            output=Path("out"),
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "config.yml"
            path.write_text(
                "\n".join(
                    [
                        "settings:",
                        "  output: old-out",
                        "# repositories:",
                        "#   - path: https://github.com/org/commented.git",
                        "#     branch: develop",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            save_wizard_config(path, state)

            rendered = path.read_text(encoding="utf-8")

        self.assertIn("# repositories:", rendered)
        self.assertIn("#   - path: https://github.com/org/commented.git", rendered)
        self.assertIn("repositories:", rendered)
        self.assertIn("path: https://github.com/org/alpha.git", rendered)

    def test_save_wizard_config_preserves_commented_entries_under_repositories(
        self,
    ) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[ref],
            selected_repositories=[SelectedRepositoryConfig(ref=ref, branch="main")],
            output=Path("out"),
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "config.yml"
            path.write_text(
                "\n".join(
                    [
                        "settings:",
                        "  output: old-out",
                        "repositories:",
                        "  - path: https://github.com/org/old.git",
                        "    branch: release",
                        "  # - path: https://github.com/org/commented.git",
                        "  #   branch: develop",
                        "  #   exclude_dirs:",
                        "  #     - node_modules",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            save_wizard_config(path, state)

            rendered = path.read_text(encoding="utf-8")

        self.assertIn("path: https://github.com/org/alpha.git", rendered)
        self.assertNotIn("path: https://github.com/org/old.git", rendered)
        self.assertIn("  # - path: https://github.com/org/commented.git", rendered)
        self.assertIn("  #   branch: develop", rendered)
        self.assertIn("  #   exclude_dirs:", rendered)
        self.assertIn("  #     - node_modules", rendered)

    def test_fetch_repository_catalog_wraps_provider_errors(self) -> None:
        target = ProviderTarget(
            key="github",
            provider="github",
            label="GitHub",
            base_url="https://api.github.com",
        )

        with patch(
            "analyze_git_repo_loc.interactive.tui_wizard.fetch_github_repositories",
            side_effect=OSError("dns failed"),
        ):
            with self.assertRaisesRegex(RemoteCatalogError, "Failed to fetch GitHub"):
                # pylint: disable-next=protected-access
                tui_wizard._fetch_repository_catalog([target], {"github": "token"})

    def test_final_review_includes_key_execution_conditions(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[ref],
            selected_repositories=[
                SelectedRepositoryConfig(
                    ref=ref,
                    branch="main",
                    cache_status="cached",
                )
            ],
            interval="monthly",
            output=Path("out"),
            no_plot_show=True,
        )

        review = render_final_review(state, detailed=True)

        self.assertIn("1 repo | monthly", review)
        self.assertIn(tr("tui.interval", value="monthly"), review)
        self.assertIn("cache=cached", review)
        self.assertIn(tr("tui.auto_display", value=tr("tui.off")), review)

    def test_compact_final_review_hides_repository_detail(self) -> None:
        ref = RemoteRepositoryRef(
            "github",
            "alpha",
            "org/alpha",
            "https://github.com/org/alpha.git",
            "",
            "https://github.com/org/alpha",
            "main",
        )
        state = TuiWizardState(
            provider_targets=[
                ProviderTarget("github", "github", "GitHub", "https://api.github.com")
            ],
            auth_tokens={},
            auth_labels={"github": "gh"},
            repository_catalog=[ref],
            selected_repositories=[
                SelectedRepositoryConfig(
                    ref=ref,
                    branch="main",
                    cache_status="cached",
                )
            ],
            recommendations=tui_wizard.LightweightRecommendations(
                languages=[
                    "Markdown",
                    "Python",
                    "YAML",
                    "JSON",
                    "Bourne Shell",
                    "TOML",
                ],
                language_source="existing cache",
            ),
        )

        review = render_final_review(state)

        self.assertIn("GitHub via gh | 1 repo | monthly", review)
        self.assertIn(
            tr(
                "tui.suggestions",
                value="Markdown, Python, YAML, JSON, Bourne Shell (+1 more)",
                source="existing cache",
            ),
            review,
        )
        self.assertIn(tr("tui.final_actions").split("   ")[0], review)
        self.assertNotIn(tr("tui.repositories"), review)
        self.assertNotIn("cache=cached", review)

    def test_normalize_final_action_supports_short_keys(self) -> None:
        self.assertEqual(normalize_final_action(""), "run")
        self.assertEqual(normalize_final_action("e"), "edit")
        self.assertEqual(normalize_final_action("i"), "select")
        self.assertEqual(normalize_final_action("details"), "details")
        self.assertEqual(normalize_final_action("s"), "save")
        self.assertEqual(normalize_final_action("x"), "save_run")
        self.assertEqual(normalize_final_action("c"), "cancel")
        self.assertIsNone(normalize_final_action("wat"))

    def test_run_wizard_steps_saves_without_running_and_returns_to_actions(self) -> None:
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[],
            selected_repositories=[],
        )
        save_callback = Mock()
        with patch(
            "analyze_git_repo_loc.interactive.tui_wizard._prompt_final_action",
            side_effect=["save", "run"],
        ):
            # pylint: disable-next=protected-access
            action = tui_wizard._run_wizard_steps(
                state,
                save_callback=save_callback,
            )

        self.assertEqual(action, "run")
        save_callback.assert_called_once_with(state)

    def test_final_action_details_returns_to_compact_action_menu(self) -> None:
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[],
            selected_repositories=[],
        )
        with patch(
            "analyze_git_repo_loc.interactive.tui_wizard._prompt",
            side_effect=["d", ""],
        ):
            with patch(
                "analyze_git_repo_loc.interactive.tui_wizard.render_final_review",
                side_effect=lambda _state, **kwargs: (
                    "detailed" if kwargs["detailed"] else "compact"
                ),
            ) as render:
                # pylint: disable-next=protected-access
                action = tui_wizard._prompt_final_action(state)

        self.assertEqual(action, "run")
        self.assertEqual(
            [call.kwargs["detailed"] for call in render.call_args_list],
            [False, True, False],
        )

    def test_final_review_color_mode_emits_ansi_sequences(self) -> None:
        state = TuiWizardState(
            provider_targets=[],
            auth_tokens={},
            repository_catalog=[],
            selected_repositories=[],
        )

        review = render_final_review(state, color=True)

        self.assertIn("\x1b[", review)


class CliOutputSummaryTests(unittest.TestCase):
    """CLI output summary formatting tests."""

    def test_format_output_summary_lists_artifacts(self) -> None:
        lines = _format_output_summary(Path("out/20260520123456"))

        self.assertNotIn(tr("output.finished"), lines)
        self.assertIn(
            tr("output.report", path=Path("out/20260520123456/report.html")),
            lines,
        )
        self.assertIn(
            tr("output.summary", path=Path("out/20260520123456/summary.md")),
            lines,
        )
        self.assertIn(
            tr("output.data", path=Path("out/20260520123456/*.csv")),
            lines,
        )


if __name__ == "__main__":
    unittest.main()
