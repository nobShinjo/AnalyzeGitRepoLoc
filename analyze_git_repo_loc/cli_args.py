"""Command-line parsing helpers.

Description:
    Builds CLI parsers and normalizes run arguments without coupling callers
    to the broader runtime utilities module. This keeps argument parsing
    focused while preserving the existing command behavior.
Functions:
    parse_arguments:
        Parse CLI arguments, merge config-backed defaults, and normalize
        values for downstream analysis commands.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

CLI_DESCRIPTION_KEY = "cli.description"
DEFAULT_CONFIG_PATH = Path("config.yml")


def _apply_display_language_from_argv(
    argv: list[str],
    *,
    resolve_display_language: Callable[[str | None], str | None],
    set_language_override: Callable[[str | None], None],
) -> None:
    """Apply a display-language override before parser help text is built."""
    for index, item in enumerate(argv):
        value: str | None = None
        if item in {"-L", "--display-language"} and index + 1 < len(argv):
            value = argv[index + 1]
        elif item.startswith("--display-language="):
            value = item.split("=", 1)[1]
        if value is None:
            continue
        try:
            set_language_override(resolve_display_language(value))
        except ValueError:
            return
        return


def _add_display_language_argument(
    parser: argparse.ArgumentParser,
    *,
    translate: Callable[..., str],
    default: str | None | object = argparse.SUPPRESS,
) -> None:
    """Add the display language option to a parser."""
    parser.add_argument(
        "-L",
        "--display-language",
        choices=["auto", "en", "jp"],
        default=default,
        help=translate("cli.display_language_help"),
    )


def parse_arguments(
    parser: argparse.ArgumentParser,
    *,
    translate: Callable[..., str],
    resolve_display_language: Callable[[str | None], str | None],
    set_language_override: Callable[[str | None], None],
    merge_yaml_config: Callable[..., argparse.Namespace],
    normalize_optional_list: Callable[[Any], list[str] | None],
    parse_optional_iso_date: Callable[[Any, str], Any],
    normalize_optional_int: Callable[[Any, str], int | None],
    validate_date_range: Callable[[Any, Any], None],
    normalize_exclude_template_mode: Callable[[Any], str],
    remote_repo_manager: Any,
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """Parse command-line arguments and normalize runtime values."""
    active_argv = list(sys.argv[1:] if argv is None else argv)
    _apply_display_language_from_argv(
        active_argv,
        resolve_display_language=resolve_display_language,
        set_language_override=set_language_override,
    )
    parser.description = translate(CLI_DESCRIPTION_KEY)
    _add_display_language_argument(
        parser,
        translate=translate,
        default="auto",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help=translate("cli.init_help"),
        description=translate(CLI_DESCRIPTION_KEY),
    )
    _add_display_language_argument(init_parser, translate=translate)
    init_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=translate("cli.init_config_help"),
    )
    init_parser.set_defaults(
        interactive=False,
        repo_paths=None,
        output=None,
        since=None,
        until=None,
        interval=None,
        lang=None,
        author_name=None,
        exclude_dirs=None,
        exclude_template_mode="auto",
        exclude_template_names=None,
        exclude_template_files=None,
        workers=None,
        clear_cache=None,
        no_plot_show=None,
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help=translate("cli.doctor_help"),
        description=translate(CLI_DESCRIPTION_KEY),
    )
    _add_display_language_argument(doctor_parser, translate=translate)
    doctor_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=translate("cli.config_help"),
    )
    doctor_parser.add_argument(
        "--remote",
        action="store_true",
        default=False,
        help=translate("cli.doctor_remote_help"),
    )
    doctor_parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help=translate("cli.doctor_strict_help"),
    )
    doctor_parser.set_defaults(
        interactive=False,
        repo_paths=None,
        output=None,
        since=None,
        until=None,
        interval=None,
        lang=None,
        author_name=None,
        exclude_dirs=None,
        exclude_template_mode="auto",
        exclude_template_names=None,
        exclude_template_files=None,
        workers=None,
        clear_cache=None,
        no_plot_show=None,
    )

    run_parser = subparsers.add_parser(
        "run",
        help=translate("cli.run_help"),
        description=translate(CLI_DESCRIPTION_KEY),
    )
    _add_display_language_argument(run_parser, translate=translate)
    run_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=translate("cli.config_help"),
    )
    run_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=translate("cli.output_help"),
    )
    run_parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        default=False,
        help=translate("cli.interactive_help"),
    )
    run_parser.add_argument(
        "--since",
        type=str,
        default=None,
        help=translate("cli.since_help"),
    )
    run_parser.add_argument(
        "--until",
        type=str,
        default=None,
        help=translate("cli.until_help"),
    )
    run_parser.add_argument(
        "--interval",
        choices=["daily", "weekly", "monthly"],
        default=None,
        help=translate("cli.interval_help"),
    )
    run_parser.add_argument(
        "--no-plot-show",
        action="store_true",
        default=None,
        help=translate("cli.no_plot_show_help"),
    )
    run_parser.set_defaults(
        repo_paths=None,
        lang=None,
        author_name=None,
        exclude_dirs=None,
        exclude_template_mode="auto",
        exclude_template_names=None,
        exclude_template_files=None,
        workers=None,
        clear_cache=None,
    )

    args = parser.parse_args(active_argv if argv is not None else None)
    set_language_override(resolve_display_language(getattr(args, "display_language", None)))
    try:
        if args.command in {"init", "doctor"}:
            return args
        args = merge_yaml_config(
            args=args,
            repo_manager=remote_repo_manager,
            normalize_list=normalize_optional_list,
        )
        args.since = parse_optional_iso_date(args.since, "--since")
        args.until = parse_optional_iso_date(args.until, "--until")
        args.lang = normalize_optional_list(args.lang)
        args.author_name = normalize_optional_list(args.author_name)
        args.exclude_dirs = normalize_optional_list(args.exclude_dirs)
        args.exclude_template_mode = normalize_exclude_template_mode(
            getattr(args, "exclude_template_mode", "auto")
        )
        args.exclude_template_names = normalize_optional_list(
            getattr(args, "exclude_template_names", None)
        )
        args.exclude_template_files = normalize_optional_list(
            getattr(args, "exclude_template_files", None)
        )
        args.workers = normalize_optional_int(args.workers, "--workers")
        if args.clear_cache is None:
            args.clear_cache = False
        if args.no_plot_show is None:
            args.no_plot_show = False
        validate_date_range(args.since, args.until)
    except ValueError as ex:
        parser.error(str(ex))
    return args
