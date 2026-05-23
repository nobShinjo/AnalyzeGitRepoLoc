"""Run the full-screen first-run configuration wizard.

Description:
    Provides the prompt_toolkit-backed `--init` wizard UI. Keeps YAML data
    generation in `init_config` and only owns editable wizard state, rendering,
    validation, and final file writing.
Classes:
    InitWizardState:
        Stores editable state for the full-screen `--init` wizard.
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

from analyze_git_repo_loc.init_config import (
    InitConfigOptions,
    build_init_config_data,
    render_init_config_yaml,
)


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
        )


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
    period = f"{state.since or '(blank)'} -> {state.until or '(blank)'}"
    excludes = ", ".join(state.exclude_dirs) if state.exclude_dirs else "(none)"
    rows = [
        ("Config", str(state.config_path)),
        ("Providers", ", ".join(providers) if providers else "(none)"),
        ("Output", str(state.output)),
        ("Interval", state.interval),
        ("Period", period),
        ("Auto display", "off" if state.no_plot_show else "on"),
        ("Cache", state.cache_policy),
        ("Exclude dirs", excludes),
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
        "Config file",
        "Providers",
        "Analysis defaults",
        "Runtime behavior",
        "Review",
    ]
    _provider_keys = ["github", "gitlab.com", "gitlab.self_hosted"]

    def __init__(self, default_path: Path) -> None:
        self.state = InitWizardState(config_path=default_path)
        self.step = 0
        self.field = 0
        self.provider_cursor = 0
        self.self_hosted_url_prompt = False
        self.message = "Create a TUI-ready YAML config for AnalyzeGitRepoLoc."
        self.confirmed = False
        self.cancelled = False

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
            return self.state.interval
        if key == "since":
            return self.state.since or ""
        if key == "until":
            return self.state.until or ""
        if key == "open_plots":
            return ""
        if key == "cache_policy":
            return self.state.cache_policy
        if key == "exclude_dirs":
            return ",".join(self.state.exclude_dirs)
        return ""

    def render(self) -> str:
        """Render the full-screen wizard content as ANSI text."""
        lines = [
            self._color("AnalyzeGitRepoLoc init wizard", Fore.CYAN + Style.BRIGHT),
            self._color(self.message, Fore.WHITE),
            "",
        ]
        for index, step_name in enumerate(self._steps):
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
                    f"{marker} [{checked}] Step {index + 1}/5 {step_name}",
                    color,
                )
            )
        lines.extend(["", self._render_step(), "", self._render_footer()])
        return "\n".join(lines)

    def move_up(self) -> None:
        """Move the cursor up inside the current selectable step."""
        if self.step == 1:
            self.provider_cursor = max(0, self.provider_cursor - 1)

    def move_down(self) -> None:
        """Move the cursor down inside the current selectable step."""
        if self.step == 1:
            self.provider_cursor = min(
                len(self._provider_keys) - 1,
                self.provider_cursor + 1,
            )

    def toggle_current_provider(self) -> None:
        """Toggle the highlighted provider checkbox."""
        if self.step != 1:
            return
        self.self_hosted_url_prompt = False
        self.state.toggle_provider(self._provider_keys[self.provider_cursor])
        self.message = "Provider selection updated."

    def back(self) -> None:
        """Move back to the previous field or step."""
        if self.step == 1 and self.self_hosted_url_prompt:
            self.self_hosted_url_prompt = False
            self.message = "Review or adjust provider selection."
            return
        if self.field > 0:
            self.field -= 1
            self.message = "Review or adjust the previous value."
            return
        if self.step == 0:
            return
        self.step -= 1
        fields = self._fields_for_current_step()
        self.field = max(0, len(fields) - 1)
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
            self.message = f"Set {fields[self.field][1]}."
            return True
        self.step += 1
        self.field = 0
        self.message = (
            "Review generated config before writing."
            if self.step == 4
            else f"Step {self.step + 1}: {self._steps[self.step]}."
        )
        return True

    def _apply_field(self, key: str, value: str) -> None:
        if key == "config_path":
            self.state.config_path = Path(value or "config.yml")
            self.state.overwrite_existing = False
            return
        if key == "overwrite":
            self.state.overwrite_existing = self._parse_bool(
                value,
                default=self.state.overwrite_existing,
            )
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
            return
        if key == "cache_policy":
            if value not in {"use", "update", "clear"}:
                raise ValueError("Invalid cache policy. Use use, update, or clear.")
            self.state.cache_policy = value
            return
        if key == "exclude_dirs":
            self.state.exclude_dirs = [
                item.strip() for item in value.split(",") if item.strip()
            ]

    def _fields_for_current_step(self) -> list[tuple[str, str]]:
        if self.step == 0:
            fields = [("config_path", "Config file path")]
            if self.state.config_path.exists():
                fields.append(
                    (
                        "overwrite",
                        (
                            f"Overwrite {self.state.config_path}? "
                            f"[{self._bool_suffix(self.state.overwrite_existing)}]"
                        ),
                    )
                )
            return fields
        if self.step == 1 and self._needs_self_hosted_url():
            return [("gitlab_base_url", "Self-hosted GitLab base URL")]
        if self.step == 2:
            return [
                ("output", "Output directory"),
                ("interval", "Analysis interval (daily/weekly/monthly)"),
                ("since", "Start date YYYY-MM-DD"),
                ("until", "End date YYYY-MM-DD"),
            ]
        if self.step == 3:
            return [
                (
                    "open_plots",
                    (
                        "Open plots automatically "
                        f"[{self._bool_suffix(not self.state.no_plot_show)}]"
                    ),
                ),
                ("cache_policy", "Cache policy (use/update/clear)"),
                ("exclude_dirs", "Common exclude directories"),
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
        if self.step == 4:
            return "\n".join(
                [
                    self._color("Config summary", Fore.CYAN + Style.BRIGHT),
                    render_init_config_summary(self.state, color=True),
                    "",
                    "Next: python -m analyze_git_repo_loc --tui --config "
                    f"{self.state.config_path}",
                ]
            )
        fields = self._fields_for_current_step()
        if not fields:
            return ""
        label = fields[self.field][1]
        return "\n".join(
            [
                self._color(label, Fore.YELLOW + Style.BRIGHT),
                "Edit the value below, then press Enter.",
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
        rows.extend(["", "Use Up/Down, Space to toggle, Enter to continue."])
        return "\n".join(rows)

    def _render_footer(self) -> str:
        if self.step == 4:
            return self._color(
                "Enter write config   Ctrl-B Back   Esc/Ctrl-C Cancel",
                Fore.YELLOW,
            )
        if self.step == 1 and not self._needs_self_hosted_url():
            return self._color(
                "Space toggle   Enter continue   Ctrl-B Back   Esc/Ctrl-C Cancel",
                Fore.YELLOW,
            )
        return self._color(
            "Enter accept value   Ctrl-B Back   Esc/Ctrl-C Cancel",
            Fore.YELLOW,
        )

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
    control = FormattedTextControl(lambda: ANSI(controller.render()))
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

    @kb.add("up", filter=provider_filter)
    def _(_: object) -> None:
        controller.move_up()

    @kb.add("down", filter=provider_filter)
    def _(_: object) -> None:
        controller.move_down()

    @kb.add(" ", filter=provider_filter)
    def _(_: object) -> None:
        controller.toggle_current_provider()

    @kb.add("c-b")
    def _(_: object) -> None:
        controller.back()
        refresh_input()

    @kb.add("enter")
    def _(_: object) -> None:
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
        print("Config initialization cancelled.")
        raise SystemExit(130)

    config_path = controller.state.config_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_data = build_init_config_data(controller.state.to_options())
    config_path.write_text(render_init_config_yaml(config_data), encoding="utf-8")
    print(
        Fore.GREEN
        + Style.BRIGHT
        + f"Created config: {config_path}"
        + Style.RESET_ALL
    )
    print(f"Next: python -m analyze_git_repo_loc --tui --config {config_path}")
    return config_path
