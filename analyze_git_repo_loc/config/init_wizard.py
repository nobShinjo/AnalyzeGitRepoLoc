"""Run the full-screen first-run configuration wizard.

Description:
    Owns the init wizard controller, step navigation, field application, and
    final file writing. Shared state/loading helpers live in
    `init_wizard_support`, while prompt_toolkit runtime wiring lives in
    `init_wizard_runtime`.

Functions:
    run_init_config_wizard:
        Run the full-screen config initialization wizard.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from colorama import Fore, Style  # pyright: ignore[reportMissingModuleSource]

from analyze_git_repo_loc.config.init_config import (
    build_init_config_data,
    render_init_config_yaml,
)
from analyze_git_repo_loc.config.init_wizard_runtime import run_prompt_toolkit_wizard
from analyze_git_repo_loc.config.init_wizard_support import (
    CACHE_POLICY_OPTIONS,
    COMMON_LANGUAGE_CHOICES,
    DEFAULT_GITLAB_BASE_URL,
    DEFAULT_INIT_CONFIG_PATH,
    EXCLUDE_TEMPLATE_CHOICES,
    EXCLUDE_TEMPLATE_MODE_OPTIONS,
    GITLAB_DOT_COM_PROVIDER_KEY,
    GITLAB_SELF_HOSTED_PROVIDER_KEY,
    INIT_SELECT_INSTRUCTIONS_KEY,
    INTERVAL_OPTIONS,
    YES_NO_OPTIONS,
    InitWizardState as _InitWizardState,
    _load_existing_init_wizard_state,
    _validate_choice,
    render_init_config_summary,
)
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.language_extensions import LanguageExtensions

InitWizardState = _InitWizardState


class _InitWizardController:
    _steps = [
        "init.step.config_file",
        "init.step.providers",
        "init.step.analysis_defaults",
        "init.step.runtime_behavior",
        "init.step.review",
    ]
    _provider_keys = [
        "github",
        GITLAB_DOT_COM_PROVIDER_KEY,
        GITLAB_SELF_HOSTED_PROVIDER_KEY,
    ]

    def __init__(self, default_path: Path) -> None:
        self.state = _load_existing_init_wizard_state(default_path)
        self.step = 0
        self.field = 0
        self.provider_cursor = 0
        self.interval_cursor = 0
        self.cache_policy_cursor = 0
        self.exclude_template_mode_cursor = 0
        self.exclude_template_cursor = 0
        self.yes_no_cursor = 0
        self.language_cursor = 0
        self.language_suggestion_cursor = 0
        self.language_query = ""
        self.self_hosted_url_prompt = False
        self.message = tr("init.initial_message")
        self.confirmed = False
        self.cancelled = False
        self._sync_cursors_to_state()

    def current_value(self) -> str:
        """Return the editable value for the current text field."""
        key = self.current_field_key()
        if key in {
            "overwrite",
            "interval",
            "open_plots",
            "cache_policy",
            "exclude_template_mode",
            "exclude_template_names",
        }:
            return ""
        if key == "config_path":
            return str(self.state.config_path)
        if key == "gitlab_base_url":
            return self.state.gitlab_base_url
        if key == "output":
            return str(self.state.output)
        if key == "languages":
            return self.language_query
        if key == "exclude_dirs":
            return ",".join(self.state.exclude_dirs)
        if key == "exclude_template_files":
            return ",".join(self.state.exclude_template_files)
        return getattr(self.state, key, None) or ""

    def render(self) -> str:
        """Render the full-screen wizard content as ANSI text."""
        lines = [
            self._color(tr("init.title"), Fore.CYAN + Style.BRIGHT),
            self._color(self.message, Fore.WHITE),
            "",
        ]
        for index, step_key in enumerate(self._steps):
            marker = ">" if index == self.step else " "
            checked = "x" if index < self.step else " "
            if index < self.step:
                color = Fore.GREEN
            elif index == self.step:
                color = Fore.CYAN
            else:
                color = ""
            lines.append(
                self._color(
                    f"{marker} [{checked}] "
                    f"{tr('init.step', current=index + 1, name=tr(step_key))}",
                    color,
                )
            )
        lines.extend(["", self._render_step(), "", self._render_footer()])
        return "\n".join(lines)

    def move_up(self) -> None:
        """Move the cursor up inside the current selectable step."""
        if self.step == 1:
            self.provider_cursor = max(0, self.provider_cursor - 1)
            return
        key = self._current_field_key()
        if key == "interval":
            self.interval_cursor = max(0, self.interval_cursor - 1)
            return
        if key == "cache_policy":
            self.cache_policy_cursor = max(0, self.cache_policy_cursor - 1)
            return
        if key == "exclude_template_mode":
            self.exclude_template_mode_cursor = max(
                0,
                self.exclude_template_mode_cursor - 1,
            )
            return
        if key == "exclude_template_names":
            self.exclude_template_cursor = max(0, self.exclude_template_cursor - 1)
            return
        if key in {"overwrite", "open_plots"}:
            self.yes_no_cursor = max(0, self.yes_no_cursor - 1)
            return
        if key == "languages" and self.language_query:
            self.language_suggestion_cursor = max(
                0,
                self.language_suggestion_cursor - 1,
            )
            return
        if key == "languages":
            self.language_cursor = max(0, self.language_cursor - 1)

    def move_down(self) -> None:
        """Move the cursor down inside the current selectable step."""
        if self.step == 1:
            self.provider_cursor = min(
                len(self._provider_keys) - 1,
                self.provider_cursor + 1,
            )
            return
        key = self._current_field_key()
        if key == "interval":
            self.interval_cursor = min(
                len(INTERVAL_OPTIONS) - 1,
                self.interval_cursor + 1,
            )
            return
        if key == "cache_policy":
            self.cache_policy_cursor = min(
                len(CACHE_POLICY_OPTIONS) - 1,
                self.cache_policy_cursor + 1,
            )
            return
        if key == "exclude_template_mode":
            self.exclude_template_mode_cursor = min(
                len(EXCLUDE_TEMPLATE_MODE_OPTIONS) - 1,
                self.exclude_template_mode_cursor + 1,
            )
            return
        if key == "exclude_template_names":
            self.exclude_template_cursor = min(
                len(EXCLUDE_TEMPLATE_CHOICES) - 1,
                self.exclude_template_cursor + 1,
            )
            return
        if key in {"overwrite", "open_plots"}:
            self.yes_no_cursor = min(
                len(YES_NO_OPTIONS) - 1,
                self.yes_no_cursor + 1,
            )
            return
        if key == "languages" and self.language_query:
            suggestions = self.language_suggestions()
            if suggestions:
                self.language_suggestion_cursor = min(
                    len(suggestions) - 1,
                    self.language_suggestion_cursor + 1,
                )
            return
        if key == "languages":
            self.language_cursor = min(
                len(self._visible_language_choices()) - 1,
                self.language_cursor + 1,
            )

    def toggle_current_provider(self) -> None:
        """Toggle the highlighted provider checkbox."""
        if self.step != 1:
            return
        self.self_hosted_url_prompt = False
        self.state.toggle_provider(self._provider_keys[self.provider_cursor])
        self.message = tr("init.provider.updated")

    def select_current_interval(self) -> None:
        """Select the highlighted interval option."""
        self.state.interval = INTERVAL_OPTIONS[self.interval_cursor]
        self.message = f"Interval set to {self.state.interval}."

    def select_current_cache_policy(self) -> None:
        """Select the highlighted cache policy option."""
        self.state.cache_policy = CACHE_POLICY_OPTIONS[self.cache_policy_cursor]
        self.message = f"Cache policy set to {self.state.cache_policy}."

    def select_current_exclude_template_mode(self) -> None:
        """Select the highlighted exclude template mode option."""
        self.state.exclude_template_mode = EXCLUDE_TEMPLATE_MODE_OPTIONS[
            self.exclude_template_mode_cursor
        ]
        self.message = (
            f"Exclude template mode set to {self.state.exclude_template_mode}."
        )

    def toggle_current_exclude_template(self) -> None:
        """Toggle the highlighted pinned exclude template checkbox."""
        if self._current_field_key() != "exclude_template_names":
            return
        self.exclude_template_cursor = min(
            self.exclude_template_cursor,
            len(EXCLUDE_TEMPLATE_CHOICES) - 1,
        )
        template_name = EXCLUDE_TEMPLATE_CHOICES[self.exclude_template_cursor]
        selected = list(self.state.exclude_template_names)
        if template_name in selected:
            selected.remove(template_name)
            self.message = f"Unpinned exclude template: {template_name}."
        else:
            selected.append(template_name)
            self.message = f"Pinned exclude template: {template_name}."
        self.state.exclude_template_names = selected

    def select_current_yes_no(self) -> None:
        """Select the highlighted yes/no value for the current field."""
        self._apply_yes_no_value(YES_NO_OPTIONS[self.yes_no_cursor] == "yes")

    def apply_yes_no_shortcut(self, key: str) -> None:
        """Apply y/n shortcut to the current yes/no field."""
        normalized = key.strip().casefold()
        if normalized == "y":
            self._apply_yes_no_value(True)
            return
        if normalized == "n":
            self._apply_yes_no_value(False)
            return
        raise ValueError("Use y or n.")

    def toggle_current_language(self) -> None:
        """Toggle the highlighted common language checkbox."""
        if self._current_field_key() != "languages":
            return
        choices = self._visible_language_choices()
        if not choices:
            return
        self.language_cursor = min(self.language_cursor, len(choices) - 1)
        language = choices[self.language_cursor]
        if language in self.state.lang:
            self.state.lang = [item for item in self.state.lang if item != language]
            self.message = f"Removed language: {language}."
            return
        self.state.lang.append(language)
        self.message = f"Added language: {language}."

    def update_language_query(self, value: str) -> None:
        """Update the language suggestion query."""
        self.language_query = value.strip()
        self._clamp_language_suggestion_cursor()

    def language_suggestions(self) -> list[str]:
        """Return supported languages matching the active query."""
        query = self.language_query.lower()
        if not query:
            return []
        common_matches = [
            language
            for language in COMMON_LANGUAGE_CHOICES
            if query in language.lower()
        ]
        selected_matches = [
            language
            for language in self.state.lang
            if query in language.lower() and language not in common_matches
        ]
        all_matches = [
            language
            for language in sorted(LanguageExtensions.language_to_extensions)
            if query in language.lower()
            and language not in common_matches
            and language not in selected_matches
        ]
        return [*common_matches, *selected_matches, *all_matches][:8]

    def toggle_selected_language_suggestion(self) -> bool:
        """Toggle the highlighted language suggestion."""
        suggestions = self.language_suggestions()
        if not suggestions:
            self.message = tr("init.language.search")
            return False
        self._clamp_language_suggestion_cursor()
        matched_language = suggestions[self.language_suggestion_cursor]
        if matched_language not in self.state.lang:
            self.state.lang.append(matched_language)
            self.message = f"Added language: {matched_language}."
        else:
            self.state.lang = [
                language for language in self.state.lang if language != matched_language
            ]
            self.message = f"Removed language: {matched_language}."
        self.language_cursor = min(
            self.language_cursor,
            max(0, len(self._visible_language_choices()) - 1),
        )
        self.language_query = ""
        self.language_suggestion_cursor = 0
        return True

    def back(self) -> None:
        """Move back to the previous field or step."""
        if self.step == 1 and self.self_hosted_url_prompt:
            self.self_hosted_url_prompt = False
            self.message = "Review or adjust provider selection."
            return
        if self._current_field_key() == "languages" and self.language_query:
            self.language_query = ""
            self.language_suggestion_cursor = 0
            self.message = "Review language defaults."
            return
        if self.field > 0:
            self.field -= 1
            self._sync_current_field_cursor()
            self.message = "Review or adjust the previous value."
            return
        if self.step == 0:
            return
        self.step -= 1
        fields = self._fields_for_current_step()
        self.field = max(0, len(fields) - 1)
        self._sync_current_field_cursor()
        self.message = "Review or adjust the previous step."

    def apply_current_input(self, value: str) -> bool:
        """Apply the current input value and advance when valid."""
        value = value.strip()
        try:
            if self.step == 1 and not self.needs_self_hosted_url():
                return self._advance_from_provider_step()
            if self.step == 4:
                self.confirmed = True
                return True
            key = self.current_field_key()
            selectors = {
                "interval": self.select_current_interval,
                "cache_policy": self.select_current_cache_policy,
                "exclude_template_mode": self.select_current_exclude_template_mode,
            }
            if key in selectors:
                return self._apply_or_select_current_field(
                    key,
                    value,
                    selectors[key],
                )
            if key == "exclude_template_names":
                return self._apply_optional_current_field(key, value)
            if key in {"overwrite", "open_plots"}:
                return self._apply_or_select_current_field(
                    key,
                    value,
                    self.select_current_yes_no,
                )
            if key == "languages":
                self._finalize_language_field()
                return True
            self._apply_field(key, value)
        except ValueError as ex:
            self.message = str(ex)
            return False
        self._advance_field()
        return True

    def cancel(self) -> None:
        """Mark the wizard as cancelled."""
        self.cancelled = True

    def _advance_from_provider_step(self) -> bool:
        if not self.state.github_enabled and not self.state.gitlab_enabled:
            self.message = "Select at least one provider."
            return False
        if self._self_hosted_selected_without_url():
            self.step = 1
            self.field = 0
            self.self_hosted_url_prompt = True
            self.message = "Enter the Self-hosted GitLab base URL."
            return True
        self.step = 2
        self.field = 0
        self.message = "Set analysis defaults."
        return True

    def _advance_field(self) -> None:
        fields = self._fields_for_current_step()
        if self.field + 1 < len(fields):
            self.field += 1
            self._sync_current_field_cursor()
            self.message = f"Set {fields[self.field][1]}."
            return
        self.step += 1
        self.field = 0
        self._sync_current_field_cursor()
        self.message = (
            "Review generated config before writing."
            if self.step == 4
            else f"Step {self.step + 1}: {self._steps[self.step]}."
        )

    def _apply_field(self, key: str, value: str) -> None:
        handlers = {
            "config_path": self._apply_config_path_field,
            "overwrite": self._apply_overwrite_field,
            "gitlab_base_url": self._apply_gitlab_base_url_field,
            "output": self._apply_output_field,
            "interval": self._apply_interval_field,
            "open_plots": self._apply_open_plots_field,
            "cache_policy": self._apply_cache_policy_field,
            "exclude_dirs": lambda raw: self._apply_csv_list_field(
                "exclude_dirs",
                raw,
            ),
            "exclude_template_mode": self._apply_exclude_template_mode_field,
            "exclude_template_names": lambda raw: self._apply_csv_list_field(
                "exclude_template_names",
                raw,
            ),
            "exclude_template_files": lambda raw: self._apply_csv_list_field(
                "exclude_template_files",
                raw,
            ),
        }
        if key in {"since", "until"}:
            self._apply_date_field(key, value)
            return
        handler = handlers.get(key)
        if handler is None:
            raise ValueError(f"Unexpected field '{key}'.")
        handler(value)

    def _apply_or_select_current_field(
        self,
        key: str,
        value: str,
        selector: Callable[[], None],
    ) -> bool:
        if value:
            self._apply_field(key, value)
        else:
            selector()
        self._advance_field()
        return True

    def _apply_optional_current_field(self, key: str, value: str) -> bool:
        if value:
            self._apply_field(key, value)
        self._advance_field()
        return True

    def _finalize_language_field(self) -> None:
        self.language_query = ""
        self.language_suggestion_cursor = 0
        self._advance_field()

    def _apply_config_path_field(self, value: str) -> None:
        self.state = _load_existing_init_wizard_state(
            Path(value or DEFAULT_INIT_CONFIG_PATH)
        )
        self.state.overwrite_existing = False
        self.language_query = ""
        self.language_suggestion_cursor = 0
        self._sync_cursors_to_state()

    def _apply_overwrite_field(self, value: str) -> None:
        self.state.overwrite_existing = self._parse_bool(
            value,
            default=self.state.overwrite_existing,
        )
        self.yes_no_cursor = 0 if self.state.overwrite_existing else 1
        if self.state.config_path.exists() and not self.state.overwrite_existing:
            self.field = 0
            raise ValueError("Enter another config path or confirm overwrite.")

    def _apply_gitlab_base_url_field(self, value: str) -> None:
        if not value:
            raise ValueError("Self-hosted GitLab base URL is required.")
        self.state.gitlab_base_url = value.rstrip("/")
        self.self_hosted_url_prompt = False

    def _apply_output_field(self, value: str) -> None:
        self.state.output = Path(value or "out")

    def _apply_interval_field(self, value: str) -> None:
        normalized = _validate_choice(value, set(INTERVAL_OPTIONS), "interval")
        self.state.interval = normalized
        self.interval_cursor = INTERVAL_OPTIONS.index(normalized)

    def _apply_date_field(self, key: str, value: str) -> None:
        parsed = self._parse_optional_date(value)
        setattr(self.state, key, parsed)

    def _apply_open_plots_field(self, value: str) -> None:
        self.state.no_plot_show = not self._parse_bool(
            value,
            default=not self.state.no_plot_show,
        )
        self.yes_no_cursor = 0 if not self.state.no_plot_show else 1

    def _apply_cache_policy_field(self, value: str) -> None:
        normalized = _validate_choice(value, set(CACHE_POLICY_OPTIONS), "cache_policy")
        self.state.cache_policy = normalized
        self.cache_policy_cursor = CACHE_POLICY_OPTIONS.index(normalized)

    def _apply_exclude_template_mode_field(self, value: str) -> None:
        self.state.exclude_template_mode = _validate_choice(
            value,
            set(EXCLUDE_TEMPLATE_MODE_OPTIONS),
            "exclude_template_mode",
        )
        self.exclude_template_mode_cursor = EXCLUDE_TEMPLATE_MODE_OPTIONS.index(
            self.state.exclude_template_mode
        )

    def _apply_csv_list_field(self, attribute: str, value: str) -> None:
        setattr(
            self.state,
            attribute,
            [item.strip() for item in value.split(",") if item.strip()],
        )

    def _fields_for_current_step(self) -> list[tuple[str, str]]:
        if self.step == 0:
            fields = [("config_path", tr("init.field.config_path"))]
            if self.state.config_path.exists():
                fields.append(
                    (
                        "overwrite",
                        tr(
                            "init.field.overwrite",
                            path=self.state.config_path,
                            suffix=self._bool_suffix(self.state.overwrite_existing),
                        ),
                    )
                )
            return fields
        if self.step == 1 and self._needs_self_hosted_url():
            return [("gitlab_base_url", tr("init.field.gitlab_base_url"))]
        if self.step == 2:
            return [
                ("output", tr("init.field.output")),
                ("interval", tr("init.interval")),
                ("languages", tr("init.default_languages")),
                ("since", tr("init.field.since")),
                ("until", tr("init.field.until")),
            ]
        if self.step == 3:
            return [
                (
                    "open_plots",
                    tr(
                        "init.field.open_plots",
                        suffix=self._bool_suffix(not self.state.no_plot_show),
                    ),
                ),
                ("cache_policy", tr("init.cache_policy")),
                ("exclude_dirs", tr("init.field.common_exclude_dirs")),
                ("exclude_template_mode", "Exclude template mode (auto/manual/off)"),
                ("exclude_template_names", "Pinned exclude templates"),
                ("exclude_template_files", "Custom exclude template files"),
            ]
        return []

    def current_field_key(self) -> str:
        """Return the active editable field key for the current step."""
        return self._current_field_key()

    def needs_self_hosted_url(self) -> bool:
        """Return whether the selected provider flow needs a self-hosted URL."""
        return self._needs_self_hosted_url()

    def _current_field_key(self) -> str:
        fields = self._fields_for_current_step()
        if not fields:
            return ""
        self.field = min(self.field, len(fields) - 1)
        return fields[self.field][0]

    def _needs_self_hosted_url(self) -> bool:
        return self.self_hosted_url_prompt

    def _self_hosted_selected_without_url(self) -> bool:
        return self.state.gitlab_enabled and not self.state.gitlab_base_url.strip()

    def _render_step(self) -> str:
        if self.step == 1 and not self._needs_self_hosted_url():
            return self._render_provider_step()
        key = self._current_field_key()
        if key == "interval":
            return self._render_interval_step()
        if key == "cache_policy":
            return self._render_cache_policy_step()
        if key == "exclude_template_mode":
            return self._render_exclude_template_mode_step()
        if key == "exclude_template_names":
            return self._render_exclude_template_names_step()
        if key in {"overwrite", "open_plots"}:
            return self._render_yes_no_step()
        if key == "languages":
            return self._render_language_step()
        if self.step == 4:
            return "\n".join(
                [
                    self._color(tr("init.config_summary"), Fore.CYAN + Style.BRIGHT),
                    render_init_config_summary(self.state, color=True),
                    "",
                    tr("init.next", path=self.state.config_path),
                ]
            )
        fields = self._fields_for_current_step()
        if not fields:
            return ""
        label = fields[self.field][1]
        return "\n".join(
            [
                self._color(label, Fore.YELLOW + Style.BRIGHT),
                tr("init.edit_value"),
            ]
        )

    def _render_provider_step(self) -> str:
        rows = []
        labels = {
            "github": "GitHub",
            GITLAB_DOT_COM_PROVIDER_KEY: "GitLab.com",
            GITLAB_SELF_HOSTED_PROVIDER_KEY: "Self-hosted GitLab",
        }
        selected = {
            "github": self.state.github_enabled,
            GITLAB_DOT_COM_PROVIDER_KEY: self.state.gitlab_enabled
            and self.state.gitlab_base_url.rstrip("/") == DEFAULT_GITLAB_BASE_URL,
            GITLAB_SELF_HOSTED_PROVIDER_KEY: self.state.gitlab_enabled
            and (
                self.self_hosted_url_prompt
                or self.state.gitlab_base_url.rstrip("/") != DEFAULT_GITLAB_BASE_URL
            ),
        }
        for index, key in enumerate(self._provider_keys):
            cursor = ">" if index == self.provider_cursor else " "
            checked = "x" if selected[key] else " "
            rows.append(f"{cursor} [{checked}] {labels[key]}")
        rows.extend(["", tr("init.provider.instructions")])
        return "\n".join(rows)

    def _render_interval_step(self) -> str:
        rows = [self._color(tr("init.interval"), Fore.YELLOW + Style.BRIGHT)]
        for index, option in enumerate(INTERVAL_OPTIONS):
            cursor = ">" if index == self.interval_cursor else " "
            checked = "x" if option == self.state.interval else " "
            rows.append(f"{cursor} [{checked}] {option}")
        rows.extend(["", tr(INIT_SELECT_INSTRUCTIONS_KEY)])
        return "\n".join(rows)

    def _render_cache_policy_step(self) -> str:
        rows = [self._color(tr("init.cache_policy"), Fore.YELLOW + Style.BRIGHT)]
        for index, option in enumerate(CACHE_POLICY_OPTIONS):
            cursor = ">" if index == self.cache_policy_cursor else " "
            checked = "x" if option == self.state.cache_policy else " "
            rows.append(f"{cursor} [{checked}] {option}")
        rows.extend(["", tr(INIT_SELECT_INSTRUCTIONS_KEY)])
        return "\n".join(rows)

    def _render_exclude_template_mode_step(self) -> str:
        rows = [self._color("Exclude template mode", Fore.YELLOW + Style.BRIGHT)]
        descriptions = {
            "auto": "detect project templates and merge them with manual excludes",
            "manual": "use only Common exclude directories; ignore templates",
            "off": "disable all exclude directories",
        }
        for index, option in enumerate(EXCLUDE_TEMPLATE_MODE_OPTIONS):
            cursor = ">" if index == self.exclude_template_mode_cursor else " "
            checked = "x" if option == self.state.exclude_template_mode else " "
            rows.append(f"{cursor} [{checked}] {option} - {descriptions[option]}")
        rows.extend(["", tr(INIT_SELECT_INSTRUCTIONS_KEY)])
        return "\n".join(rows)

    def _render_exclude_template_names_step(self) -> str:
        rows = [
            self._color("Pinned exclude templates", Fore.YELLOW + Style.BRIGHT),
            "Optional. Leave all unchecked to auto-detect templates from each repository.",
        ]
        for index, option in enumerate(EXCLUDE_TEMPLATE_CHOICES):
            cursor = ">" if index == self.exclude_template_cursor else " "
            checked = "x" if option in self.state.exclude_template_names else " "
            rows.append(f"{cursor} [{checked}] {option}")
        rows.extend(["", "Up/Down move   Space toggle   Enter continue"])
        return "\n".join(rows)

    def _render_yes_no_step(self) -> str:
        label = self._fields_for_current_step()[self.field][1]
        current_value = self._current_yes_no_value()
        rows = [self._color(label, Fore.YELLOW + Style.BRIGHT)]
        for index, option in enumerate(YES_NO_OPTIONS):
            cursor = ">" if index == self.yes_no_cursor else " "
            checked = "x" if (option == "yes") == current_value else " "
            rows.append(f"{cursor} [{checked}] {option}")
        rows.extend(["", tr("init.yes_no.instructions")])
        return "\n".join(rows)

    def _render_language_step(self) -> str:
        rows = [self._color(tr("init.default_languages"), Fore.YELLOW + Style.BRIGHT)]
        for index, language in enumerate(self._visible_language_choices()):
            cursor = ">" if index == self.language_cursor else " "
            checked = "x" if language in self.state.lang else " "
            rows.append(f"{cursor} - [{checked}] {language}")
        selected = (
            ", ".join(self.state.lang) if self.state.lang else tr("init.value.all")
        )
        rows.extend(["", tr("init.selected", value=selected)])
        rows.extend(self._render_language_query_section())
        return "\n".join(rows)

    def _render_language_query_section(self) -> list[str]:
        if not self.language_query:
            return [
                tr("init.language.search"),
                tr("init.language.instructions"),
            ]
        rows = [tr("init.suggestions")]
        suggestions = self.language_suggestions()
        if suggestions:
            for index, language in enumerate(suggestions):
                cursor = ">" if index == self.language_suggestion_cursor else " "
                checked = "x" if language in self.state.lang else " "
                rows.append(f"{cursor} [{checked}] {language}")
        else:
            rows.append(tr("init.language.suggestion_empty"))
        rows.append(tr("init.language.suggestion_instructions"))
        return rows

    def _render_footer(self) -> str:
        if self.step == 4:
            return self._color(
                tr("init.footer.review"),
                Fore.YELLOW,
            )
        if self.step == 1 and not self._needs_self_hosted_url():
            return self._color(
                tr("init.footer.provider"),
                Fore.YELLOW,
            )
        key = self._current_field_key()
        if key == "interval":
            return self._color(
                tr("init.footer.interval"),
                Fore.YELLOW,
            )
        if key == "cache_policy":
            return self._color(
                tr("init.footer.interval"),
                Fore.YELLOW,
            )
        if key in {"overwrite", "open_plots"}:
            return self._color(
                tr("init.footer.yes_no"),
                Fore.YELLOW,
            )
        if key == "languages" and self.language_query:
            return self._color(
                tr("init.footer.language_suggestion"),
                Fore.YELLOW,
            )
        if key == "languages":
            return self._color(
                tr("init.footer.language"),
                Fore.YELLOW,
            )
        return self._color(
            tr("init.footer.enter_value"),
            Fore.YELLOW,
        )

    def _clamp_language_suggestion_cursor(self) -> None:
        suggestions = self.language_suggestions()
        if not suggestions:
            self.language_suggestion_cursor = 0
            return
        self.language_suggestion_cursor = min(
            self.language_suggestion_cursor,
            len(suggestions) - 1,
        )

    def _visible_language_choices(self) -> list[str]:
        choices = list(COMMON_LANGUAGE_CHOICES)
        choices.extend(
            language
            for language in self.state.lang
            if language not in COMMON_LANGUAGE_CHOICES
        )
        return choices

    def _sync_cursors_to_state(self) -> None:
        self.interval_cursor = INTERVAL_OPTIONS.index(self.state.interval)
        self.cache_policy_cursor = CACHE_POLICY_OPTIONS.index(self.state.cache_policy)
        self.exclude_template_mode_cursor = EXCLUDE_TEMPLATE_MODE_OPTIONS.index(
            self.state.exclude_template_mode
        )
        self.yes_no_cursor = 0 if self._current_yes_no_value(default=True) else 1
        self.language_cursor = min(
            self.language_cursor,
            max(0, len(self._visible_language_choices()) - 1),
        )

    def _sync_current_field_cursor(self) -> None:
        key = self._current_field_key()
        if key == "interval":
            self.interval_cursor = INTERVAL_OPTIONS.index(self.state.interval)
            return
        if key == "cache_policy":
            self.cache_policy_cursor = CACHE_POLICY_OPTIONS.index(
                self.state.cache_policy
            )
            return
        if key == "exclude_template_mode":
            self.exclude_template_mode_cursor = EXCLUDE_TEMPLATE_MODE_OPTIONS.index(
                self.state.exclude_template_mode
            )
            return
        if key == "exclude_template_names":
            self.exclude_template_cursor = min(
                self.exclude_template_cursor,
                max(0, len(EXCLUDE_TEMPLATE_CHOICES) - 1),
            )
            return
        if key in {"overwrite", "open_plots"}:
            self.yes_no_cursor = 0 if self._current_yes_no_value() else 1
            return
        if key == "languages":
            self.language_cursor = min(
                self.language_cursor,
                max(0, len(self._visible_language_choices()) - 1),
            )

    def _current_yes_no_value(self, *, default: bool | None = None) -> bool:
        key = self._current_field_key()
        if key == "overwrite":
            return self.state.overwrite_existing
        if key == "open_plots":
            return not self.state.no_plot_show
        if default is not None:
            return default
        raise ValueError("Current field is not a yes/no field.")

    def _apply_yes_no_value(self, value: bool) -> None:
        key = self._current_field_key()
        if key == "overwrite":
            self.state.overwrite_existing = value
            self.yes_no_cursor = 0 if value else 1
            self.message = f"Overwrite set to {'yes' if value else 'no'}."
            return
        if key == "open_plots":
            self.state.no_plot_show = not value
            self.yes_no_cursor = 0 if value else 1
            self.message = (
                f"Open plots automatically set to {'yes' if value else 'no'}."
            )
            return
        raise ValueError("Current field is not a yes/no field.")

    @staticmethod
    def _parse_optional_date(value: str) -> str | None:
        if not value:
            return None
        try:
            datetime.fromisoformat(value)
        except ValueError as ex:
            raise ValueError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from ex
        return value

    @staticmethod
    def _parse_bool(value: str, *, default: bool) -> bool:
        if not value:
            return default
        normalized = value.lower()
        if normalized in {"y", "yes", "true", "1", "on"}:
            return True
        if normalized in {"n", "no", "false", "0", "off"}:
            return False
        raise ValueError("Use y or n.")

    @staticmethod
    def _bool_suffix(default: bool) -> str:
        return "Y/n" if default else "y/N"

    @staticmethod
    def _color(text: str, color: object) -> str:
        if not color:
            return text
        return f"{color}{text}{Style.RESET_ALL}"


def run_init_config_wizard(default_path: Path = DEFAULT_INIT_CONFIG_PATH) -> Path:
    """Run the full-screen config initialization wizard.

    Args:
        default_path (Path): Default config output path.

    Returns:
        Path: Written config file path.
    """
    controller = _InitWizardController(default_path)
    run_prompt_toolkit_wizard(controller)
    if controller.cancelled or not controller.confirmed:
        print(tr("init.cancelled"))
        raise SystemExit(130)

    config_path = controller.state.config_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_data = build_init_config_data(controller.state.to_options())
    existing_text = (
        config_path.read_text(encoding="utf-8") if config_path.exists() else None
    )
    config_path.write_text(
        render_init_config_yaml(config_data, existing_text=existing_text),
        encoding="utf-8",
    )
    print(
        f"{Fore.GREEN}{Style.BRIGHT}"
        f"{tr('init.created_config', path=config_path)}"
        f"{Style.RESET_ALL}"
    )
    print(tr("init.next", path=config_path))
    return config_path
