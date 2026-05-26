"""Run the full-screen first-run configuration wizard.

Description:
    Provides the prompt_toolkit-backed `init` wizard UI. Keeps YAML data
    generation in `init_config` and only owns editable wizard state, rendering,
    validation, and final file writing.
Classes:
    InitWizardState:
        Stores editable state for the full-screen `init` wizard.
Functions:
    render_init_config_summary:
        Render a concise final summary for generated config values.
    run_init_config_wizard:
        Run the full-screen config initialization wizard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from colorama import Fore, Style, just_fix_windows_console

from analyze_git_repo_loc.exclude_templates import BUILTIN_EXCLUDE_TEMPLATES
from analyze_git_repo_loc.init_config import (
    InitConfigOptions,
    build_init_config_data,
    render_init_config_yaml,
)
from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.language_extensions import LanguageExtensions
from analyze_git_repo_loc.yaml_config import load_yaml_data


INTERVAL_OPTIONS = ["daily", "weekly", "monthly"]
CACHE_POLICY_OPTIONS = ["use", "update", "clear"]
EXCLUDE_TEMPLATE_MODE_OPTIONS = ["auto", "manual", "off"]
EXCLUDE_TEMPLATE_CHOICES = [
    template.name for template in sorted(BUILTIN_EXCLUDE_TEMPLATES, key=lambda item: item.priority)
]
YES_NO_OPTIONS = ["yes", "no"]
COMMON_LANGUAGE_CHOICES = [
    "C#",
    "Python",
    "C++",
    "C",
    "Java",
    "JavaScript",
    "TypeScript",
    "Go",
    "Rust",
    "Kotlin",
    "PHP",
    "Ruby",
]


@dataclass
class InitWizardState:
    """Editable state for the full-screen first-run config wizard."""

    config_path: Path = Path("config.yml")
    overwrite_existing: bool = False
    github_enabled: bool = True
    gitlab_enabled: bool = False
    gitlab_base_url: str = "https://gitlab.com"
    output: Path = Path("out")
    interval: str = "monthly"
    since: str | None = None
    until: str | None = None
    no_plot_show: bool = True
    cache_policy: str = "use"
    exclude_dirs: list[str] = field(default_factory=lambda: ["node_modules", ".venv"])
    exclude_template_mode: str = "auto"
    exclude_template_names: list[str] = field(default_factory=list)
    exclude_template_files: list[str] = field(default_factory=list)
    lang: list[str] = field(default_factory=list)

    def toggle_provider(self, key: str) -> None:
        """Toggle a provider checkbox while keeping GitLab targets exclusive."""
        if key == "github":
            self.github_enabled = not self.github_enabled
            return
        if key == "gitlab.com":
            if self.gitlab_enabled and self.gitlab_base_url == "https://gitlab.com":
                self.gitlab_enabled = False
                return
            self.gitlab_enabled = True
            self.gitlab_base_url = "https://gitlab.com"
            return
        if key == "gitlab.self_hosted":
            if self.gitlab_enabled and self.gitlab_base_url != "https://gitlab.com":
                self.gitlab_enabled = False
                self.gitlab_base_url = "https://gitlab.com"
                return
            self.gitlab_enabled = True
            self.gitlab_base_url = ""
            return
        raise ValueError(f"Unsupported provider key '{key}'.")

    def to_options(self) -> InitConfigOptions:
        """Convert wizard state to generated config options."""
        return InitConfigOptions(
            github_enabled=self.github_enabled,
            gitlab_enabled=self.gitlab_enabled,
            gitlab_base_url=self.gitlab_base_url or "https://gitlab.com",
            output=self.output,
            interval=self.interval,
            since=self.since,
            until=self.until,
            no_plot_show=self.no_plot_show,
            cache_policy=self.cache_policy,
            exclude_dirs=self.exclude_dirs,
            exclude_template_mode=self.exclude_template_mode,
            exclude_template_names=self.exclude_template_names,
            exclude_template_files=self.exclude_template_files,
            lang=self.lang,
        )


def _load_existing_init_wizard_state(config_path: Path) -> InitWizardState:
    """Load existing config values into first-run wizard state."""
    state = InitWizardState(config_path=config_path)
    if not config_path.exists():
        return state

    config_data = load_yaml_data(config_path)
    settings = _as_mapping(config_data.get("settings"), "settings")
    interactive = _as_mapping(config_data.get("interactive"), "interactive")
    providers = _as_mapping(interactive.get("providers"), "interactive.providers")
    quick_defaults = _as_mapping(
        interactive.get("quick_defaults"),
        "interactive.quick_defaults",
    )

    _apply_provider_defaults(state, providers)
    state.output = Path(_pick_existing_value(settings, quick_defaults, "output", "out"))
    state.interval = _validate_choice(
        str(_pick_existing_value(settings, quick_defaults, "interval", "monthly")),
        {"daily", "weekly", "monthly"},
        "interval",
    )
    state.since = _normalize_optional_date(
        _pick_existing_value(settings, quick_defaults, "since", None)
    )
    state.until = _normalize_optional_date(
        _pick_existing_value(settings, quick_defaults, "until", None)
    )
    state.lang = _normalize_string_list(
        _pick_existing_value(settings, quick_defaults, "lang", [])
    )
    state.no_plot_show = _normalize_bool(
        _pick_existing_value(settings, quick_defaults, "no_plot_show", True),
        "no_plot_show",
    )
    state.cache_policy = _validate_choice(
        str(quick_defaults.get("cache_policy") or "use").strip().casefold(),
        {"use", "update", "clear"},
        "cache_policy",
    )
    state.exclude_dirs = _normalize_string_list(
        quick_defaults.get("exclude_dirs", settings.get("exclude_dirs"))
    ) or ["node_modules", ".venv"]
    state.exclude_template_mode = _validate_choice(
        quick_defaults.get(
            "exclude_template_mode",
            settings.get("exclude_template_mode", "auto"),
        ),
        {"auto", "manual", "off"},
        "exclude_template_mode",
    )
    state.exclude_template_names = _normalize_string_list(
        quick_defaults.get(
            "exclude_template_names",
            settings.get("exclude_template_names"),
        )
    ) or []
    state.exclude_template_files = _normalize_string_list(
        quick_defaults.get(
            "exclude_template_files",
            settings.get("exclude_template_files"),
        )
    ) or []
    return state


def _as_mapping(value: object, key: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"YAML config '{key}' must be a mapping.")
    return value


def _pick_existing_value(
    settings: dict,
    quick_defaults: dict,
    key: str,
    default: object,
) -> object:
    value = settings.get(key)
    if value is not None and value != "":
        return value
    value = quick_defaults.get(key)
    if value is not None and value != "":
        return value
    return default


def _normalize_optional_date(value: object) -> str | None:
    if value is None or value == "":
        return None
    normalized = str(value)
    try:
        datetime.fromisoformat(normalized)
    except ValueError as ex:
        raise ValueError(f"Invalid date '{normalized}'. Use YYYY-MM-DD.") from ex
    return normalized


def _normalize_string_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError(f"Expected a string or list value, got {type(value).__name__}.")


def _normalize_bool(value: object, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "yes", "on", "y"}:
            return True
        if normalized in {"0", "false", "no", "off", "n"}:
            return False
    raise ValueError(f"Invalid {key} value '{value}'.")


def _validate_choice(value: str, choices: set[str], key: str) -> str:
    normalized = value.strip().casefold()
    if normalized not in choices:
        raise ValueError(f"Invalid {key} value '{value}'.")
    return normalized


def _apply_provider_defaults(state: InitWizardState, providers: dict) -> None:
    github = _as_mapping(providers.get("github"), "interactive.providers.github")
    gitlab = _as_mapping(providers.get("gitlab"), "interactive.providers.gitlab")
    if "enabled" in github:
        state.github_enabled = _normalize_bool(github["enabled"], "github.enabled")
    if "enabled" in gitlab:
        state.gitlab_enabled = _normalize_bool(gitlab["enabled"], "gitlab.enabled")
    if gitlab.get("base_url"):
        state.gitlab_base_url = str(gitlab["base_url"]).rstrip("/")


def render_init_config_summary(state: InitWizardState, *, color: bool = False) -> str:
    """Render a concise summary of the config that will be written.

    Args:
        state (InitWizardState): Wizard state to summarize.
        color (bool): If True, color labels and values for console display.

    Returns:
        str: Human-readable summary.
    """
    providers: list[str] = []
    if state.github_enabled:
        providers.append("GitHub")
    if state.gitlab_enabled:
        label = (
            "GitLab.com"
            if state.gitlab_base_url.rstrip("/") == "https://gitlab.com"
            else "Self-hosted GitLab"
        )
        providers.append(label)
    period = f"{state.since or tr('init.value.blank')} -> {state.until or tr('init.value.blank')}"
    excludes = ", ".join(state.exclude_dirs) if state.exclude_dirs else tr("init.value.none")
    template_names = (
        ", ".join(state.exclude_template_names)
        if state.exclude_template_names
        else tr("init.value.blank")
    )
    languages = ", ".join(state.lang) if state.lang else tr("init.value.all")
    rows = [
        (tr("init.label.config"), str(state.config_path)),
        (tr("init.label.providers"), ", ".join(providers) if providers else tr("init.value.none")),
        (tr("init.label.output"), str(state.output)),
        (tr("init.label.interval"), state.interval),
        (tr("init.label.languages"), languages),
        (tr("init.label.period"), period),
        (tr("init.label.auto_display"), tr("tui.off") if state.no_plot_show else tr("tui.on")),
        (tr("init.label.cache"), state.cache_policy),
        (tr("init.label.exclude_dirs"), excludes),
        ("Exclude template mode", state.exclude_template_mode),
        ("Exclude templates", template_names),
    ]
    if color:
        label_style = Fore.CYAN + Style.BRIGHT
        value_style = Fore.WHITE + Style.BRIGHT
        return "\n".join(
            [
                f"{label_style}{label}:{Style.RESET_ALL} "
                f"{value_style}{value}{Style.RESET_ALL}"
                for label, value in rows
            ]
        )
    return "\n".join(
        [f"{label}: {value}" for label, value in rows]
    )


class _InitWizardController:
    _steps = [
        "init.step.config_file",
        "init.step.providers",
        "init.step.analysis_defaults",
        "init.step.runtime_behavior",
        "init.step.review",
    ]
    _provider_keys = ["github", "gitlab.com", "gitlab.self_hosted"]

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
        key = self._current_field_key()
        if key == "config_path":
            return str(self.state.config_path)
        if key == "overwrite":
            return ""
        if key == "gitlab_base_url":
            return self.state.gitlab_base_url
        if key == "output":
            return str(self.state.output)
        if key == "interval":
            return ""
        if key == "languages":
            return self.language_query
        if key == "since":
            return self.state.since or ""
        if key == "until":
            return self.state.until or ""
        if key == "open_plots":
            return ""
        if key == "cache_policy":
            return ""
        if key == "exclude_template_mode":
            return ""
        if key == "exclude_dirs":
            return ",".join(self.state.exclude_dirs)
        if key == "exclude_template_names":
            return ""
        if key == "exclude_template_files":
            return ",".join(self.state.exclude_template_files)
        return ""

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
            color = (
                Fore.GREEN
                if index < self.step
                else Fore.CYAN
                if index == self.step
                else ""
            )
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
            if query in language.lower()
            and language not in common_matches
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
            if self.step == 1 and not self._needs_self_hosted_url():
                return self._advance_from_provider_step()
            if self.step == 4:
                self.confirmed = True
                return True
            key = self._current_field_key()
            if key == "interval":
                if value:
                    self._apply_field(key, value)
                else:
                    self.select_current_interval()
                return self._advance_field()
            if key == "cache_policy":
                if value:
                    self._apply_field(key, value)
                else:
                    self.select_current_cache_policy()
                return self._advance_field()
            if key == "exclude_template_mode":
                if value:
                    self._apply_field(key, value)
                else:
                    self.select_current_exclude_template_mode()
                return self._advance_field()
            if key == "exclude_template_names":
                if value:
                    self._apply_field(key, value)
                return self._advance_field()
            if key in {"overwrite", "open_plots"}:
                if value:
                    self._apply_field(key, value)
                else:
                    self.select_current_yes_no()
                return self._advance_field()
            if key == "languages":
                self.language_query = ""
                self.language_suggestion_cursor = 0
                return self._advance_field()
            self._apply_field(self._current_field_key(), value)
        except ValueError as ex:
            self.message = str(ex)
            return False
        return self._advance_field()

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

    def _advance_field(self) -> bool:
        fields = self._fields_for_current_step()
        if self.field + 1 < len(fields):
            self.field += 1
            self._sync_current_field_cursor()
            self.message = f"Set {fields[self.field][1]}."
            return True
        self.step += 1
        self.field = 0
        self._sync_current_field_cursor()
        self.message = (
            "Review generated config before writing."
            if self.step == 4
            else f"Step {self.step + 1}: {self._steps[self.step]}."
        )
        return True

    def _apply_field(self, key: str, value: str) -> None:
        if key == "config_path":
            self.state = _load_existing_init_wizard_state(Path(value or "config.yml"))
            self.state.overwrite_existing = False
            self.language_query = ""
            self.language_suggestion_cursor = 0
            self._sync_cursors_to_state()
            return
        if key == "overwrite":
            self.state.overwrite_existing = self._parse_bool(
                value,
                default=self.state.overwrite_existing,
            )
            self.yes_no_cursor = 0 if self.state.overwrite_existing else 1
            if self.state.config_path.exists() and not self.state.overwrite_existing:
                self.field = 0
                raise ValueError("Enter another config path or confirm overwrite.")
            return
        if key == "gitlab_base_url":
            if not value:
                raise ValueError("Self-hosted GitLab base URL is required.")
            self.state.gitlab_base_url = value.rstrip("/")
            self.self_hosted_url_prompt = False
            return
        if key == "output":
            self.state.output = Path(value or "out")
            return
        if key == "interval":
            if value not in {"daily", "weekly", "monthly"}:
                raise ValueError("Invalid interval. Use daily, weekly, or monthly.")
            self.state.interval = value
            self.interval_cursor = INTERVAL_OPTIONS.index(value)
            return
        if key in {"since", "until"}:
            parsed = self._parse_optional_date(value)
            setattr(self.state, key, parsed)
            return
        if key == "open_plots":
            self.state.no_plot_show = not self._parse_bool(
                value,
                default=not self.state.no_plot_show,
            )
            self.yes_no_cursor = 0 if not self.state.no_plot_show else 1
            return
        if key == "cache_policy":
            if value not in {"use", "update", "clear"}:
                raise ValueError("Invalid cache policy. Use use, update, or clear.")
            self.state.cache_policy = value
            self.cache_policy_cursor = CACHE_POLICY_OPTIONS.index(value)
            return
        if key == "exclude_dirs":
            self.state.exclude_dirs = [
                item.strip() for item in value.split(",") if item.strip()
            ]
            return
        if key == "exclude_template_mode":
            self.state.exclude_template_mode = _validate_choice(
                value,
                set(EXCLUDE_TEMPLATE_MODE_OPTIONS),
                "exclude_template_mode",
            )
            self.exclude_template_mode_cursor = EXCLUDE_TEMPLATE_MODE_OPTIONS.index(
                self.state.exclude_template_mode
            )
            return
        if key == "exclude_template_names":
            self.state.exclude_template_names = [
                item.strip() for item in value.split(",") if item.strip()
            ]
            return
        if key == "exclude_template_files":
            self.state.exclude_template_files = [
                item.strip() for item in value.split(",") if item.strip()
            ]

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
            "gitlab.com": "GitLab.com",
            "gitlab.self_hosted": "Self-hosted GitLab",
        }
        selected = {
            "github": self.state.github_enabled,
            "gitlab.com": self.state.gitlab_enabled
            and self.state.gitlab_base_url.rstrip("/") == "https://gitlab.com",
            "gitlab.self_hosted": self.state.gitlab_enabled
            and (
                self.self_hosted_url_prompt
                or self.state.gitlab_base_url.rstrip("/") != "https://gitlab.com"
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
        rows.extend(["", tr("init.select.instructions")])
        return "\n".join(rows)

    def _render_cache_policy_step(self) -> str:
        rows = [self._color(tr("init.cache_policy"), Fore.YELLOW + Style.BRIGHT)]
        for index, option in enumerate(CACHE_POLICY_OPTIONS):
            cursor = ">" if index == self.cache_policy_cursor else " "
            checked = "x" if option == self.state.cache_policy else " "
            rows.append(f"{cursor} [{checked}] {option}")
        rows.extend(["", tr("init.select.instructions")])
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
        rows.extend(["", tr("init.select.instructions")])
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
        selected = ", ".join(self.state.lang) if self.state.lang else tr("init.value.all")
        rows.extend(["", tr("init.selected", value=selected)])
        if self.language_query:
            rows.append(tr("init.suggestions"))
            suggestions = self.language_suggestions()
            if suggestions:
                for index, language in enumerate(suggestions):
                    cursor = ">" if index == self.language_suggestion_cursor else " "
                    checked = "x" if language in self.state.lang else " "
                    rows.append(f"{cursor} [{checked}] {language}")
            else:
                rows.append(tr("init.language.suggestion_empty"))
            rows.append(tr("init.language.suggestion_instructions"))
        else:
            rows.append(tr("init.language.search"))
            rows.append(tr("init.language.instructions"))
        return "\n".join(rows)

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
            self.message = f"Open plots automatically set to {'yes' if value else 'no'}."
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
    def _color(text: str, color: str) -> str:
        if not color:
            return text
        return f"{color}{text}{Style.RESET_ALL}"


def run_init_config_wizard(default_path: Path = Path("config.yml")) -> Path:
    """Run the full-screen config initialization wizard.

    Args:
        default_path (Path): Default config output path.

    Returns:
        Path: Written config file path.
    """
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.widgets import TextArea
    except ImportError as ex:
        raise RuntimeError(
            "prompt_toolkit is required for --init. "
            "Install dependencies with `uv sync --active`."
        ) from ex

    just_fix_windows_console()
    controller = _InitWizardController(default_path)
    input_field = TextArea(height=1, prompt="Value: ", multiline=False)
    input_field.text = controller.current_value()

    def render_control() -> object:
        if controller._current_field_key() == "languages":
            controller.update_language_query(input_field.text)
        return ANSI(controller.render())

    control = FormattedTextControl(render_control)
    kb = KeyBindings()
    app: Application | None = None

    def refresh_input() -> None:
        value = controller.current_value()
        input_field.text = value
        input_field.buffer.cursor_position = len(value)
        if app is not None:
            app.invalidate()

    provider_filter = Condition(
        lambda: controller.step == 1 and not controller._needs_self_hosted_url()
    )
    interval_filter = Condition(lambda: controller._current_field_key() == "interval")
    cache_policy_filter = Condition(
        lambda: controller._current_field_key() == "cache_policy"
    )
    exclude_template_mode_filter = Condition(
        lambda: controller._current_field_key() == "exclude_template_mode"
    )
    exclude_template_names_filter = Condition(
        lambda: controller._current_field_key() == "exclude_template_names"
    )
    yes_no_filter = Condition(
        lambda: controller._current_field_key() in {"overwrite", "open_plots"}
    )
    language_filter = Condition(lambda: controller._current_field_key() == "languages")
    selection_filter = (
        provider_filter
        | interval_filter
        | cache_policy_filter
        | exclude_template_mode_filter
        | exclude_template_names_filter
        | yes_no_filter
        | language_filter
    )

    @kb.add("up", filter=selection_filter)
    def _(_: object) -> None:
        controller.move_up()
        refresh_input()

    @kb.add("down", filter=selection_filter)
    def _(_: object) -> None:
        controller.move_down()
        refresh_input()

    @kb.add(" ", filter=provider_filter)
    def _(_: object) -> None:
        controller.toggle_current_provider()
        refresh_input()

    @kb.add(" ", filter=interval_filter)
    def _(_: object) -> None:
        controller.select_current_interval()
        refresh_input()

    @kb.add(" ", filter=cache_policy_filter)
    def _(_: object) -> None:
        controller.select_current_cache_policy()
        refresh_input()

    @kb.add(" ", filter=exclude_template_mode_filter)
    def _(_: object) -> None:
        controller.select_current_exclude_template_mode()
        refresh_input()

    @kb.add(" ", filter=exclude_template_names_filter)
    def _(_: object) -> None:
        controller.toggle_current_exclude_template()
        refresh_input()

    @kb.add(" ", filter=yes_no_filter)
    def _(_: object) -> None:
        controller.select_current_yes_no()
        refresh_input()

    @kb.add("y", filter=yes_no_filter)
    def _(_: object) -> None:
        controller.apply_yes_no_shortcut("y")
        refresh_input()

    @kb.add("n", filter=yes_no_filter)
    def _(_: object) -> None:
        controller.apply_yes_no_shortcut("n")
        refresh_input()

    @kb.add(" ", filter=language_filter)
    def _(_: object) -> None:
        controller.update_language_query(input_field.text)
        if controller.language_query:
            controller.toggle_selected_language_suggestion()
        else:
            controller.toggle_current_language()
        refresh_input()

    @kb.add("c-b")
    def _(_: object) -> None:
        controller.back()
        refresh_input()

    @kb.add("enter")
    def _(_: object) -> None:
        if language_filter():
            controller.update_language_query(input_field.text)
        if controller.apply_current_input(input_field.text):
            if controller.confirmed and app is not None:
                app.exit()
                return
            refresh_input()

    @kb.add("escape")
    @kb.add("c-c")
    def _(_: object) -> None:
        controller.cancel()
        if app is not None:
            app.exit()

    application = Application(
        layout=Layout(
            HSplit(
                [
                    Window(content=control, always_hide_cursor=True),
                    input_field,
                ]
            )
        ),
        key_bindings=kb,
        full_screen=True,
    )
    app = application
    application.run()
    if controller.cancelled or not controller.confirmed:
        print(tr("init.cancelled"))
        raise SystemExit(130)

    config_path = controller.state.config_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_data = build_init_config_data(controller.state.to_options())
    config_path.write_text(render_init_config_yaml(config_data), encoding="utf-8")
    print(
        Fore.GREEN
        + Style.BRIGHT
        + tr("init.created_config", path=config_path)
        + Style.RESET_ALL
    )
    print(tr("init.next", path=config_path))
    return config_path
