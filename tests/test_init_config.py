"""Tests for first-run config initialization."""

from __future__ import annotations

# pylint: disable=missing-function-docstring,protected-access

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from colorama import Fore, Style

from analyze_git_repo_loc.__main__ import _format_output_summary
from analyze_git_repo_loc.config.init_config import (
    InitConfigOptions,
    build_init_config_data,
    render_init_config_yaml,
    resolve_init_config_path,
)
from analyze_git_repo_loc.config.init_wizard_runtime import (
    _build_register_refresh_handler,
)
from analyze_git_repo_loc.config.init_wizard import (
    InitWizardState,
    _InitWizardController,
    render_init_config_summary,
)
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.utils import parse_arguments


class InitConfigGenerationTests(unittest.TestCase):
    """Config data and YAML rendering tests."""

    def test_builds_minimal_interactive_ready_config_without_repositories_or_secrets(
        self,
    ) -> None:
        options = InitConfigOptions(
            github_enabled=True,
            gitlab_enabled=False,
            output=Path("out"),
            interval="monthly",
            since="2024-01-01",
            until="2026-05-31",
            no_plot_show=True,
            cache_policy="use",
            exclude_dirs=["node_modules", ".venv"],
        )

        config = build_init_config_data(options)

        self.assertNotIn("repositories", config)
        self.assertEqual(config["settings"]["output"], "out")
        self.assertEqual(config["settings"]["interval"], "monthly")
        self.assertEqual(config["settings"]["since"], "2024-01-01")
        self.assertEqual(config["settings"]["until"], "2026-05-31")
        self.assertTrue(config["settings"]["no_plot_show"])
        self.assertFalse(config["settings"]["clear_cache"])
        self.assertNotIn("tui", config)
        self.assertTrue(config["interactive"]["providers"]["github"]["enabled"])
        self.assertFalse(config["interactive"]["providers"]["gitlab"]["enabled"])
        self.assertEqual(
            config["interactive"]["quick_defaults"]["exclude_dirs"],
            ["node_modules", ".venv"],
        )
        self.assertEqual(config["settings"]["exclude_template_mode"], "auto")
        self.assertEqual(
            config["interactive"]["quick_defaults"]["exclude_template_mode"],
            "auto",
        )
        self.assertNotIn("lang", config["settings"])
        self.assertNotIn("lang", config["interactive"]["quick_defaults"])
        rendered = repr(config)
        self.assertNotIn("TOKEN", rendered)
        self.assertNotIn("client_id", rendered)
        self.assertNotIn("auth", rendered)

    def test_render_init_config_yaml_round_trips_with_yaml_parser(self) -> None:
        config = build_init_config_data(
            InitConfigOptions(
                github_enabled=True,
                gitlab_enabled=True,
                output=Path("reports"),
                interval="weekly",
                since=None,
                until=None,
                no_plot_show=False,
                cache_policy="clear",
                exclude_dirs=[],
            )
        )

        rendered = render_init_config_yaml(config)
        loaded = yaml.safe_load(rendered)

        self.assertEqual(loaded, config)
        self.assertTrue(rendered.endswith("\n"))
        self.assertNotIn("repositories:", rendered)

    def test_self_hosted_gitlab_config_uses_custom_base_url(self) -> None:
        config = build_init_config_data(
            InitConfigOptions(
                github_enabled=False,
                gitlab_enabled=True,
                gitlab_base_url="https://gitlab.example.com",
            )
        )

        self.assertFalse(config["interactive"]["providers"]["github"]["enabled"])
        self.assertTrue(config["interactive"]["providers"]["gitlab"]["enabled"])
        self.assertEqual(
            config["interactive"]["providers"]["gitlab"]["base_url"],
            "https://gitlab.example.com",
        )

    def test_language_defaults_are_saved_for_batch_and_interactive_runs(self) -> None:
        config = build_init_config_data(
            InitConfigOptions(
                lang=["C#", "Python"],
            )
        )

        self.assertEqual(config["settings"]["lang"], ["C#", "Python"])
        self.assertEqual(
            config["interactive"]["quick_defaults"]["lang"],
            ["C#", "Python"],
        )

    def test_exclude_template_defaults_are_saved_for_batch_and_interactive_runs(self) -> None:
        config = build_init_config_data(
            InitConfigOptions(
                exclude_template_mode="auto",
                exclude_template_names=["python"],
                exclude_template_files=["exclude-templates.yml"],
            )
        )

        self.assertEqual(config["settings"]["exclude_template_mode"], "auto")
        self.assertEqual(config["settings"]["exclude_template_names"], ["python"])
        self.assertEqual(
            config["settings"]["exclude_template_files"],
            ["exclude-templates.yml"],
        )
        self.assertEqual(
            config["interactive"]["quick_defaults"]["exclude_template_names"],
            ["python"],
        )


class InitWizardStateTests(unittest.TestCase):
    """Full-screen init wizard state tests."""

    def test_gitlab_targets_are_mutually_exclusive(self) -> None:
        state = InitWizardState()

        state.toggle_provider("gitlab.com")
        self.assertTrue(state.gitlab_enabled)
        self.assertEqual(state.gitlab_base_url, "https://gitlab.com")

        state.toggle_provider("gitlab.self_hosted")
        self.assertTrue(state.gitlab_enabled)
        self.assertEqual(state.gitlab_base_url, "")

        state.toggle_provider("gitlab.com")
        self.assertTrue(state.gitlab_enabled)
        self.assertEqual(state.gitlab_base_url, "https://gitlab.com")

    def test_summary_lists_selected_config_values(self) -> None:
        state = InitWizardState(
            config_path=Path("custom.yml"),
            github_enabled=False,
            gitlab_enabled=True,
            gitlab_base_url="https://gitlab.example.com",
            output=Path("reports"),
            interval="weekly",
            since="2026-01-01",
            until="2026-05-01",
            no_plot_show=False,
            cache_policy="update",
            exclude_dirs=["node_modules"],
            lang=["C#", "Python"],
        )

        summary = render_init_config_summary(state)

        self.assertIn(f"{tr('init.label.config')}: custom.yml", summary)
        self.assertIn(f"{tr('init.label.providers')}: Self-hosted GitLab", summary)
        self.assertIn(f"{tr('init.label.output')}: reports", summary)
        self.assertIn(f"{tr('init.label.interval')}: weekly", summary)
        self.assertIn(f"{tr('init.label.period')}: 2026-01-01 -> 2026-05-01", summary)
        self.assertIn(f"{tr('init.label.auto_display')}: {tr('tui.on')}", summary)
        self.assertIn(f"{tr('init.label.cache')}: update", summary)
        self.assertIn(f"{tr('init.label.exclude_dirs')}: node_modules", summary)
        self.assertIn(f"{tr('init.label.languages')}: C#, Python", summary)

    def test_interval_field_renders_as_select_options(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 1

        rendered = controller.render()

        self.assertIn("[x] monthly", rendered)
        self.assertIn("[ ] weekly", rendered)
        self.assertIn(tr("init.select.instructions"), rendered)
        self.assertNotIn("Edit the value below", rendered)

    def test_interval_selection_updates_state(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 1

        controller.move_up()
        controller.select_current_interval()

        self.assertEqual(controller.state.interval, "weekly")

    def test_cache_policy_field_renders_as_select_options(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 3
        controller.field = 1

        rendered = controller.render()

        self.assertIn("[x] use", rendered)
        self.assertIn("[ ] update", rendered)
        self.assertIn(tr("init.select.instructions"), rendered)
        self.assertNotIn("Edit the value below", rendered)

    def test_cache_policy_selection_updates_state(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 3
        controller.field = 1

        controller.move_down()
        controller.select_current_cache_policy()

        self.assertEqual(controller.state.cache_policy, "update")

    def test_exclude_template_mode_renders_as_select_options(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 3
        controller.field = 3

        rendered = controller.render()

        self.assertIn("[x] auto", rendered)
        self.assertIn("[ ] manual", rendered)
        self.assertIn("use only Common exclude directories", rendered)
        self.assertIn(tr("init.select.instructions"), rendered)
        self.assertNotIn("Edit the value below", rendered)

    def test_exclude_template_mode_selection_updates_state(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 3
        controller.field = 3

        controller.move_down()
        controller.select_current_exclude_template_mode()

        self.assertEqual(controller.state.exclude_template_mode, "manual")

    def test_pinned_exclude_templates_render_as_checkboxes(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 3
        controller.field = 4

        rendered = controller.render()

        self.assertIn("Pinned exclude templates", rendered)
        self.assertIn("[ ] unity", rendered)
        self.assertIn("Leave all unchecked to auto-detect", rendered)
        self.assertNotIn("Edit the value below", rendered)

    def test_pinned_exclude_template_toggle_updates_state(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 3
        controller.field = 4

        controller.toggle_current_exclude_template()

        self.assertEqual(controller.state.exclude_template_names, ["unity"])

    def test_language_field_renders_common_language_checkboxes(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 2

        rendered = controller.render()

        self.assertIn("[ ] C#", rendered)
        self.assertIn("[ ] Python", rendered)
        self.assertIn(tr("init.language.search"), rendered)

    def test_language_toggle_updates_state(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 2
        controller.language_cursor = 1

        controller.toggle_current_language()

        self.assertEqual(controller.state.lang, ["Python"])

    def test_language_suggestions_match_input_text(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 2

        controller.update_language_query("script")

        self.assertIn("JavaScript", controller.language_suggestions())
        self.assertIn("TypeScript", controller.language_suggestions())

    def test_language_suggestion_cursor_moves_inside_input_mode(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 2
        controller.update_language_query("script")

        controller.move_down()

        self.assertEqual(controller.language_suggestion_cursor, 1)

    def test_selected_language_suggestion_can_be_added(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 2
        controller.update_language_query("script")
        controller.move_down()

        self.assertTrue(controller.toggle_selected_language_suggestion())

        self.assertEqual(controller.state.lang, ["TypeScript"])
        self.assertEqual(controller.language_query, "")

    def test_language_input_render_highlights_selected_suggestion(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 2
        controller.update_language_query("script")
        controller.move_down()

        rendered = controller.render()

        self.assertIn("> [ ] TypeScript", rendered)

    def test_selected_suggestion_renders_as_language_checkbox(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 2
        controller.update_language_query("powershell")

        controller.toggle_selected_language_suggestion()

        rendered = controller.render()

        self.assertIn("[x] PowerShell", rendered)

    def test_selected_language_suggestion_can_be_removed(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 2
        controller.state.lang = ["PowerShell"]
        controller.update_language_query("powershell")

        controller.toggle_selected_language_suggestion()

        self.assertEqual(controller.state.lang, [])
        self.assertEqual(controller.language_query, "")

    def test_enter_from_language_field_advances_without_adding_exact_match(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 2
        controller.update_language_query("PowerShell")

        controller.apply_current_input(controller.current_value())

        self.assertEqual(controller.state.lang, [])
        self.assertEqual(controller.field, 3)

    def test_supported_language_input_adds_matching_language(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 2

        controller.update_language_query("PowerShell")
        self.assertTrue(controller.toggle_selected_language_suggestion())

        self.assertEqual(controller.state.lang, ["PowerShell"])

    def test_unsupported_language_input_is_rejected(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 2

        controller.update_language_query("MadeUpLang")
        self.assertFalse(controller.toggle_selected_language_suggestion())

        self.assertEqual(controller.state.lang, [])
        self.assertEqual(controller.language_query, "MadeUpLang")
        self.assertIn(tr("init.language.search"), controller.message)

    def test_existing_config_populates_init_wizard_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text(
                "\n".join(
                    [
                        "settings:",
                        "  output: reports",
                        "  interval: weekly",
                        "  since: '2026-01-01'",
                        "  until: '2026-05-01'",
                        "  lang:",
                        "    - Python",
                        "  no_plot_show: false",
                        "interactive:",
                        "  providers:",
                        "    github:",
                        "      enabled: false",
                        "    gitlab:",
                        "      enabled: true",
                        "      base_url: https://gitlab.example.com",
                        "  quick_defaults:",
                        "    cache_policy: update",
                        "    exclude_dirs:",
                        "      - node_modules",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            controller = _InitWizardController(config_path)

        self.assertFalse(controller.state.github_enabled)
        self.assertTrue(controller.state.gitlab_enabled)
        self.assertEqual(controller.state.gitlab_base_url, "https://gitlab.example.com")
        self.assertEqual(controller.state.output, Path("reports"))
        self.assertEqual(controller.state.interval, "weekly")
        self.assertEqual(controller.state.since, "2026-01-01")
        self.assertEqual(controller.state.until, "2026-05-01")
        self.assertEqual(controller.state.lang, ["Python"])
        self.assertFalse(controller.state.no_plot_show)
        self.assertEqual(controller.state.cache_policy, "update")
        self.assertEqual(controller.state.exclude_dirs, ["node_modules"])

    def test_existing_config_uses_quick_defaults_when_settings_are_blank(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text(
                "\n".join(
                    [
                        "settings:",
                        "  output: reports",
                        "interactive:",
                        "  quick_defaults:",
                        "    output: quick-out",
                        "    interval: daily",
                        "    since: '2026-02-01'",
                        "    until: '2026-03-01'",
                        "    lang:",
                        "      - Rust",
                        "    no_plot_show: true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            controller = _InitWizardController(config_path)

        self.assertEqual(controller.state.output, Path("reports"))
        self.assertEqual(controller.state.interval, "daily")
        self.assertEqual(controller.state.since, "2026-02-01")
        self.assertEqual(controller.state.until, "2026-03-01")
        self.assertEqual(controller.state.lang, ["Rust"])
        self.assertTrue(controller.state.no_plot_show)

    def test_back_moves_to_previous_field_inside_current_step(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 2
        controller.field = 3

        controller.back()

        self.assertEqual(controller.step, 2)
        self.assertEqual(controller.field, 2)

    def test_back_from_self_hosted_url_returns_to_provider_checklist(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 1
        controller.state.gitlab_enabled = True
        controller.state.gitlab_base_url = ""
        controller.self_hosted_url_prompt = True

        controller.back()

        self.assertEqual(controller.step, 1)
        self.assertIn("Self-hosted GitLab", controller.render())
        self.assertIn("[x] Self-hosted GitLab", controller.render())

    def test_cancel_finishes_without_keyboard_interrupt_traceback(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))

        controller.cancel()

        self.assertTrue(controller.cancelled)
        self.assertFalse(controller.confirmed)

    def test_bool_field_renders_as_yes_no_select_options(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 3
        controller.state.no_plot_show = False

        self.assertEqual(controller.current_value(), "")
        self.assertIn("[x] yes", controller.render())
        self.assertIn("[ ] no", controller.render())
        self.assertIn(tr("init.yes_no.instructions"), controller.render())

    def test_yes_no_shortcuts_update_bool_field(self) -> None:
        controller = _InitWizardController(Path("missing-test-config.yml"))
        controller.step = 3
        controller.state.no_plot_show = False

        controller.apply_yes_no_shortcut("n")

        self.assertTrue(controller.state.no_plot_show)

        controller.apply_yes_no_shortcut("y")

        self.assertFalse(controller.state.no_plot_show)

    def test_overwrite_renders_as_yes_no_select_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yml"
            config_path.write_text("existing: true\n", encoding="utf-8")
            controller = _InitWizardController(config_path)
            controller.state.overwrite_existing = True
            controller.field = 1

            self.assertEqual(controller.current_value(), "")
            self.assertIn(
                tr(
                    "init.field.overwrite",
                    path=config_path,
                    suffix=controller._bool_suffix(controller.state.overwrite_existing),
                ),
                controller.render(),
            )
            self.assertIn("[x] yes", controller.render())
            self.assertIn("[ ] no", controller.render())

            controller.apply_yes_no_shortcut("n")

        self.assertFalse(controller.state.overwrite_existing)

    def test_colored_summary_styles_labels_and_values(self) -> None:
        state = InitWizardState(config_path=Path("config.yml"))

        summary = render_init_config_summary(state, color=True)

        self.assertIn(
            f"{Fore.CYAN}{Style.BRIGHT}{tr('init.label.config')}:{Style.RESET_ALL}",
            summary,
        )
        self.assertIn(
            f"{Fore.WHITE}{Style.BRIGHT}config.yml{Style.RESET_ALL}",
            summary,
        )


class InitWizardRuntimeTests(unittest.TestCase):
    """prompt_toolkit runtime helper tests."""

    def test_register_refresh_handler_omits_filter_when_not_provided(self) -> None:
        class FakeKeyBindings:
            def __init__(self) -> None:
                self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

            def add(self, *args: object, **kwargs: object):
                self.calls.append((args, kwargs))

                def decorator(func: object) -> object:
                    return func

                return decorator

        key_bindings = FakeKeyBindings()
        register_refresh_handler = _build_register_refresh_handler(
            key_bindings,
            lambda: None,
        )

        register_refresh_handler("c-b", lambda: None)

        self.assertEqual(key_bindings.calls, [(("c-b",), {})])


class InitConfigPathTests(unittest.TestCase):
    """Config path selection safety tests."""

    def test_uses_default_config_path_when_it_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            default_path = Path(tmp_dir) / "config.yml"

            resolved = resolve_init_config_path(
                default_path=default_path,
                prompt=lambda _message: self.fail("prompt should not be called"),
                confirm_overwrite=lambda _path: self.fail(
                    "confirm should not be called"
                ),
            )

        self.assertEqual(resolved, default_path)

    def test_existing_default_prompts_for_alternate_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            default_path = Path(tmp_dir) / "config.yml"
            default_path.write_text("existing: true\n", encoding="utf-8")

            resolved = resolve_init_config_path(
                default_path=default_path,
                prompt=lambda _message: "custom.yml",
                confirm_overwrite=lambda _path: self.fail(
                    "confirm should not be called"
                ),
            )

        self.assertEqual(resolved, Path(tmp_dir) / "custom.yml")

    def test_existing_same_path_requires_overwrite_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            default_path = Path(tmp_dir) / "config.yml"
            default_path.write_text("existing: true\n", encoding="utf-8")

            resolved = resolve_init_config_path(
                default_path=default_path,
                prompt=lambda _message: "config.yml",
                confirm_overwrite=lambda path: path == default_path,
            )

        self.assertEqual(resolved, default_path)

    def test_declined_overwrite_returns_to_path_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            default_path = Path(tmp_dir) / "config.yml"
            default_path.write_text("existing: true\n", encoding="utf-8")
            answers = iter(["config.yml", "safe.yml"])

            resolved = resolve_init_config_path(
                default_path=default_path,
                prompt=lambda _message: next(answers),
                confirm_overwrite=lambda _path: False,
            )

        self.assertEqual(resolved, Path(tmp_dir) / "safe.yml")


class InitConfigCliTests(unittest.TestCase):
    """CLI dispatch tests for init subcommand."""

    def test_init_subcommand_uses_default_config_path(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")

        with patch.object(sys, "argv", ["analyze_git_repo_loc", "init"]):
            args = parse_arguments(parser)

        self.assertEqual(args.command, "init")
        self.assertEqual(args.config, Path("config.yml"))
        self.assertIsNone(args.repo_paths)

    def test_legacy_init_flag_is_rejected(self) -> None:
        parser = argparse.ArgumentParser(prog="analyze_git_repo_loc")

        with patch.object(sys, "argv", ["analyze_git_repo_loc", "--init"]):
            with self.assertRaises(SystemExit) as ctx:
                parse_arguments(parser)

        self.assertEqual(ctx.exception.code, 2)


class OutputSummaryTests(unittest.TestCase):
    """Final output summary formatting tests."""

    def test_output_summary_lists_report_data_charts_and_cache(self) -> None:
        output_root = Path("out")
        output_dir = output_root / "20260522010101"

        lines = _format_output_summary(output_dir=output_dir, output_root=output_root)

        self.assertNotIn(tr("output.finished"), lines)
        self.assertIn(tr("output.report", path=output_dir / "report.html"), lines)
        self.assertIn(tr("output.summary", path=output_dir / "summary.md"), lines)
        self.assertIn(tr("output.run_data", path=output_dir), lines)
        self.assertIn(tr("output.repository_charts", path=output_root), lines)
        self.assertIn(tr("output.cache", path=output_root / ".cache"), lines)
