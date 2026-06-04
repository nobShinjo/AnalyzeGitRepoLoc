"""Support types and helpers for the init wizard.

Description:
    Holds shared constants, editable wizard state, YAML-backed default loading,
    and summary rendering for the full-screen init wizard. This keeps the main
    controller module focused on navigation and field application.

Classes:
    InitWizardState:
        Stores editable state for the full-screen `init` wizard.
Functions:
    render_init_config_summary:
        Render a concise final summary for generated config values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from colorama import Fore, Style

from analyze_git_repo_loc.analysis.exclude_templates import BUILTIN_EXCLUDE_TEMPLATES
from analyze_git_repo_loc.config.init_config import InitConfigOptions
from analyze_git_repo_loc.config.yaml_config import load_yaml_data
from analyze_git_repo_loc.i18n import tr

INTERVAL_OPTIONS = ["daily", "weekly", "monthly"]
CACHE_POLICY_OPTIONS = ["use", "update", "clear"]
EXCLUDE_TEMPLATE_MODE_OPTIONS = ["auto", "manual", "off"]
EXCLUDE_TEMPLATE_CHOICES = [
    template.name
    for template in sorted(BUILTIN_EXCLUDE_TEMPLATES, key=lambda item: item.priority)
]
YES_NO_OPTIONS = ["yes", "no"]
INIT_SELECT_INSTRUCTIONS_KEY = "init.select.instructions"
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
DEFAULT_INIT_CONFIG_PATH = Path("config.yml")
DEFAULT_GITLAB_BASE_URL = "https://gitlab.com"
GITLAB_DOT_COM_PROVIDER_KEY = "gitlab.com"
GITLAB_SELF_HOSTED_PROVIDER_KEY = "gitlab.self_hosted"


@dataclass
class InitWizardState:
    """Editable state for the full-screen first-run config wizard."""

    config_path: Path = DEFAULT_INIT_CONFIG_PATH
    overwrite_existing: bool = False
    github_enabled: bool = True
    gitlab_enabled: bool = False
    gitlab_base_url: str = DEFAULT_GITLAB_BASE_URL
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
        if key == GITLAB_DOT_COM_PROVIDER_KEY:
            if self.gitlab_enabled and self.gitlab_base_url == DEFAULT_GITLAB_BASE_URL:
                self.gitlab_enabled = False
                return
            self.gitlab_enabled = True
            self.gitlab_base_url = DEFAULT_GITLAB_BASE_URL
            return
        if key == GITLAB_SELF_HOSTED_PROVIDER_KEY:
            if self.gitlab_enabled and self.gitlab_base_url != DEFAULT_GITLAB_BASE_URL:
                self.gitlab_enabled = False
                self.gitlab_base_url = DEFAULT_GITLAB_BASE_URL
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
            gitlab_base_url=self.gitlab_base_url or DEFAULT_GITLAB_BASE_URL,
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
    state.output = Path(
        str(_pick_existing_value(settings, quick_defaults, "output", "out"))
    )
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
    state.exclude_template_names = (
        _normalize_string_list(
            quick_defaults.get(
                "exclude_template_names",
                settings.get("exclude_template_names"),
            )
        )
        or []
    )
    state.exclude_template_files = (
        _normalize_string_list(
            quick_defaults.get(
                "exclude_template_files",
                settings.get("exclude_template_files"),
            )
        )
        or []
    )
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
    """Render a concise summary of the config that will be written."""
    providers: list[str] = []
    if state.github_enabled:
        providers.append("GitHub")
    if state.gitlab_enabled:
        label = (
            "GitLab.com"
            if state.gitlab_base_url.rstrip("/") == DEFAULT_GITLAB_BASE_URL
            else "Self-hosted GitLab"
        )
        providers.append(label)
    period = f"{state.since or tr('init.value.blank')} -> {state.until or tr('init.value.blank')}"
    excludes = (
        ", ".join(state.exclude_dirs) if state.exclude_dirs else tr("init.value.none")
    )
    template_names = (
        ", ".join(state.exclude_template_names)
        if state.exclude_template_names
        else tr("init.value.blank")
    )
    languages = ", ".join(state.lang) if state.lang else tr("init.value.all")
    rows = [
        (tr("init.label.config"), str(state.config_path)),
        (
            tr("init.label.providers"),
            ", ".join(providers) if providers else tr("init.value.none"),
        ),
        (tr("init.label.output"), str(state.output)),
        (tr("init.label.interval"), state.interval),
        (tr("init.label.languages"), languages),
        (tr("init.label.period"), period),
        (
            tr("init.label.auto_display"),
            tr("tui.off") if state.no_plot_show else tr("tui.on"),
        ),
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
    return "\n".join([f"{label}: {value}" for label, value in rows])
