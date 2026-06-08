"""Create first-run YAML configuration files.

Description:
    Provides the interactive `init` setup flow for creating a minimal
    interactive-ready YAML configuration file. Keeps authentication secrets and
    repository selections out of generated config files.
Classes:
    InitConfigOptions:
        Stores non-secret defaults selected during first-run setup.
Functions:
    build_init_config_data:
        Convert setup options into YAML-ready config data.
    render_init_config_yaml:
        Render generated config data as YAML text.
    resolve_init_config_path:
        Select a safe config output path with overwrite confirmation.
    run_init_config_wizard:
        Delegate to the full-screen config initialization wizard.
    run_init_config:
        Run the interactive config initialization flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from analyze_git_repo_loc.config.yaml_preservation import preserve_repository_blocks
from analyze_git_repo_loc.i18n import tr

PromptFunc = Callable[[str], str]
ConfirmFunc = Callable[[Path], bool]


@dataclass(frozen=True)
class InitConfigOptions:
    """Non-secret first-run configuration choices."""

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


def build_init_config_data(options: InitConfigOptions) -> dict[str, Any]:
    """Build a minimal interactive-ready config mapping.

    Args:
        options (InitConfigOptions): First-run configuration choices.

    Returns:
        dict[str, Any]: YAML-ready config data.
    """
    settings: dict[str, Any] = {
        "output": str(options.output),
        "interval": options.interval,
        "clear_cache": False,
        "no_plot_show": options.no_plot_show,
        "exclude_template_mode": options.exclude_template_mode,
    }
    if options.exclude_template_names:
        settings["exclude_template_names"] = options.exclude_template_names
    if options.exclude_template_files:
        settings["exclude_template_files"] = options.exclude_template_files
    if options.since:
        settings["since"] = options.since
    if options.until:
        settings["until"] = options.until
    if options.lang:
        settings["lang"] = options.lang

    quick_defaults: dict[str, Any] = {
        "interval": options.interval,
        "cache_policy": options.cache_policy,
        "no_plot_show": options.no_plot_show,
        "exclude_dirs": options.exclude_dirs,
        "exclude_template_mode": options.exclude_template_mode,
    }
    if options.exclude_template_names:
        quick_defaults["exclude_template_names"] = options.exclude_template_names
    if options.exclude_template_files:
        quick_defaults["exclude_template_files"] = options.exclude_template_files
    if options.lang:
        quick_defaults["lang"] = options.lang

    return {
        "settings": settings,
        "interactive": {
            "providers": {
                "github": {
                    "enabled": options.github_enabled,
                    "api_base_url": "https://api.github.com",
                },
                "gitlab": {
                    "enabled": options.gitlab_enabled,
                    "base_url": options.gitlab_base_url.rstrip("/"),
                },
            },
            "defaults": {
                "clone_protocol": "https",
            },
            "quick_defaults": quick_defaults,
        },
    }


def render_init_config_yaml(
    config_data: dict[str, Any],
    *,
    existing_text: str | None = None,
) -> str:
    """Render config data as YAML text.

    Args:
        config_data (dict[str, Any]): YAML-ready config data.
        existing_text (str | None): Existing YAML content to preserve selected blocks.

    Returns:
        str: Rendered YAML ending with a newline.
    """
    rendered = yaml.safe_dump(
        config_data,
        allow_unicode=False,
        default_flow_style=False,
        sort_keys=False,
    )
    if isinstance(rendered, bytes):
        rendered_text = rendered.decode("utf-8")
        return preserve_repository_blocks(
            rendered_text,
            existing_text,
            preserve_active=True,
        )
    if rendered is None:
        raise TypeError("yaml.safe_dump returned no YAML text.")
    return preserve_repository_blocks(rendered, existing_text, preserve_active=True)


def resolve_init_config_path(
    *,
    default_path: Path,
    prompt: PromptFunc,
    confirm_overwrite: ConfirmFunc,
) -> Path:
    """Resolve a safe output path for generated config.

    Args:
        default_path (Path): Default config file path.
        prompt (PromptFunc): Input function for alternate paths.
        confirm_overwrite (ConfirmFunc): Confirmation function for overwrites.

    Returns:
        Path: Selected config path.
    """
    if not default_path.exists():
        return default_path

    base_dir = default_path.parent
    while True:
        answer = prompt(
            f"{default_path} already exists. Enter another config file path: "
        ).strip()
        candidate = Path(answer) if answer else default_path
        if not candidate.is_absolute():
            candidate = base_dir / candidate
        if candidate.exists():
            if confirm_overwrite(candidate):
                return candidate
            continue
        return candidate


def _prompt_bool(prompt: PromptFunc, message: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    answer = prompt(f"{message} [{suffix}]: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "true", "1"}


def _prompt_text(prompt: PromptFunc, message: str, default: str) -> str:
    answer = prompt(f"{message} [{default}]: ").strip()
    return answer or default


def _prompt_optional_date(prompt: PromptFunc, message: str) -> str | None:
    answer = prompt(f"{message} [blank]: ").strip()
    if not answer:
        return None
    try:
        datetime.fromisoformat(answer)
    except ValueError as ex:
        raise ValueError(f"Invalid date '{answer}'. Use YYYY-MM-DD.") from ex
    return answer


def _prompt_interval(prompt: PromptFunc) -> str:
    interval = _prompt_text(prompt, "Analysis interval (daily/weekly/monthly)", "monthly")
    if interval not in {"daily", "weekly", "monthly"}:
        raise ValueError("Invalid interval. Use daily, weekly, or monthly.")
    return interval


def _prompt_cache_policy(prompt: PromptFunc) -> str:
    cache_policy = _prompt_text(prompt, "Cache policy (use/update/clear)", "use")
    if cache_policy not in {"use", "update", "clear"}:
        raise ValueError("Invalid cache policy. Use use, update, or clear.")
    return cache_policy


def _prompt_exclude_dirs(prompt: PromptFunc) -> list[str]:
    raw_value = _prompt_text(prompt, "Common exclude directories", "node_modules,.venv")
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _prompt_languages(prompt: PromptFunc) -> list[str]:
    raw_value = prompt("Default language filter [blank for all]: ").strip()
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _default_confirm_overwrite(path: Path) -> bool:
    answer = input(f"Overwrite {path}? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def run_init_config_wizard(default_path: Path = Path("config.yml")) -> Path:
    """Run the full-screen config initialization wizard.

    Args:
        default_path (Path): Default config output path.

    Returns:
        Path: Written config file path.
    """
    from analyze_git_repo_loc.config.init_wizard import run_init_config_wizard as run_wizard

    return run_wizard(default_path)


def run_init_config(
    *,
    default_path: Path = Path("config.yml"),
    prompt: PromptFunc = input,
    confirm_overwrite: ConfirmFunc = _default_confirm_overwrite,
) -> Path:
    """Run interactive config initialization and write the YAML file.

    Args:
        default_path (Path): Default config output path.
        prompt (PromptFunc): Input function for interactive prompts.
        confirm_overwrite (ConfirmFunc): Confirmation function for overwrites.

    Returns:
        Path: Written config file path.
    """
    config_path = resolve_init_config_path(
        default_path=default_path,
        prompt=prompt,
        confirm_overwrite=confirm_overwrite,
    )
    github_enabled = _prompt_bool(prompt, "Enable GitHub provider", True)
    gitlab_enabled = _prompt_bool(prompt, "Enable GitLab provider", False)
    output = Path(_prompt_text(prompt, "Output directory", "out"))
    interval = _prompt_interval(prompt)
    lang = _prompt_languages(prompt)
    since = _prompt_optional_date(prompt, "Start date YYYY-MM-DD")
    until = _prompt_optional_date(prompt, "End date YYYY-MM-DD")
    no_plot_show = not _prompt_bool(prompt, "Open plots automatically", False)
    cache_policy = _prompt_cache_policy(prompt)
    exclude_dirs = _prompt_exclude_dirs(prompt)

    config_data = build_init_config_data(
        InitConfigOptions(
            github_enabled=github_enabled,
            gitlab_enabled=gitlab_enabled,
            output=output,
            interval=interval,
            lang=lang,
            since=since,
            until=until,
            no_plot_show=no_plot_show,
            cache_policy=cache_policy,
            exclude_dirs=exclude_dirs,
        )
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    existing_text = (
        config_path.read_text(encoding="utf-8") if config_path.exists() else None
    )
    config_path.write_text(
        render_init_config_yaml(config_data, existing_text=existing_text),
        encoding="utf-8",
    )
    print(tr("init.created_config", path=config_path))
    print(tr("init.next", path=config_path))
    return config_path
