"""Locale-based translations for user-facing text.

Description:
    Provides lightweight en/jp text lookup without adding gettext build steps.
    The active language is inferred from the operating system locale; Japanese
    locales use jp, and all other locales fall back to English.
Functions:
    resolve_language:
        Resolve a locale string to a supported language code.
    current_language:
        Return the language inferred from the current OS locale.
    tr:
        Translate a message key with optional format arguments.
"""

from __future__ import annotations

import locale
from typing import Any


SUPPORTED_LANGUAGES = {"en", "jp"}

_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "auth.device.code": "Code: {code}",
        "auth.device.open": "Open: {uri}",
        "auth.device.required": "OAuth Device Code login is required.",
        "auth.device.waiting": "Waiting for authorization in the browser...",
        "auth.enter_number": "Enter a number from the list.",
        "auth.gitlab_client_id_prompt": (
            "GitLab OAuth Application ID for this run: "
        ),
        "auth.not_available": "{label} is not available.",
        "auth.provider_title": "{provider} authentication",
        "cli.config_help": "YAML configuration file path (default: config.yml).",
        "cli.description": "Analyze Git repositories and visualize code LOC.",
        "cli.init_config_help": (
            "YAML configuration file path to create (default: config.yml)."
        ),
        "cli.init_help": "Create an initial YAML configuration file interactively.",
        "cli.interactive_help": (
            "Review and adjust analysis settings interactively before running."
        ),
        "cli.interval_help": "Interval (default: monthly)",
        "cli.no_plot_show_help": "If set, the plots will not be shown.",
        "cli.output_help": "Output path",
        "cli.run_help": (
            "Run analysis from a YAML configuration file, optionally interactively."
        ),
        "cli.since_help": "Start Date yyyy-mm-dd",
        "cli.until_help": "End Date yyyy-mm-dd",
        "error.message": "Error message: {message}",
        "error.stack_trace": "Stack trace:",
        "error.type": "Error type: {type}",
        "error.unexpected": "An unexpected error occurred:",
        "init.cache_policy": "Cache policy",
        "init.cancelled": "Config initialization cancelled.",
        "init.created_config": "Created config: {path}",
        "init.footer.enter_value": "Enter accept value   Ctrl-B Back   Esc/Ctrl-C Cancel",
        "init.footer.interval": "Up/Down move   Space select   Enter continue   Ctrl-B Back",
        "init.footer.language": "Type search   Space toggle   Enter continue   Ctrl-B Back",
        "init.footer.language_suggestion": (
            "Up/Down move   Space toggle suggestion   Enter continue"
        ),
        "init.footer.review": "Enter write config   Ctrl-B Back   Esc/Ctrl-C Cancel",
        "init.footer.yes_no": "Up/Down move   Space select   Y/N shortcut   Ctrl-B Back",
        "init.language.instructions": (
            "Use Up/Down, Space to toggle, Enter to continue."
        ),
        "init.language.search": "Type to search supported languages.",
        "init.language.suggestion_empty": "- Type to search supported languages.",
        "init.language.suggestion_instructions": (
            "Use Up/Down, Space to toggle a suggested language."
        ),
        "init.next": "Next: python -m analyze_git_repo_loc run -i --config {path}",
        "init.provider.instructions": (
            "Use Up/Down, Space to toggle, Enter to continue."
        ),
        "init.provider.updated": "Provider selection updated.",
        "init.select.instructions": "Use Up/Down, Space to select, Enter to continue.",
        "init.title": "AnalyzeGitRepoLoc init wizard",
        "init.yes_no.instructions": (
            "Use Up/Down, Space to select. Y/N shortcut available."
        ),
        "output.finished": "Finished",
        "warnings.title": "Warnings:",
    },
    "jp": {
        "auth.device.code": "コード: {code}",
        "auth.device.open": "開く: {uri}",
        "auth.device.required": "OAuth Device Code ログインが必要です。",
        "auth.device.waiting": "ブラウザーでの認可を待機しています...",
        "auth.enter_number": "一覧の番号を入力してください。",
        "auth.gitlab_client_id_prompt": (
            "この実行で使う GitLab OAuth Application ID: "
        ),
        "auth.not_available": "{label} は利用できません。",
        "auth.provider_title": "{provider} 認証",
        "cli.config_help": "YAML 設定ファイルのパス (既定: config.yml)。",
        "cli.description": "Git リポジトリを解析し、コード LOC を可視化します。",
        "cli.init_config_help": (
            "作成する YAML 設定ファイルのパス (既定: config.yml)。"
        ),
        "cli.init_help": "初期 YAML 設定ファイルを対話形式で作成します。",
        "cli.interactive_help": (
            "解析前に対話形式で設定を確認・調整します。"
        ),
        "cli.interval_help": "集計間隔 (既定: monthly)",
        "cli.no_plot_show_help": "指定するとプロットを自動表示しません。",
        "cli.output_help": "出力パス",
        "cli.run_help": "YAML 設定ファイルから解析を実行します。対話実行も可能です。",
        "cli.since_help": "開始日 yyyy-mm-dd",
        "cli.until_help": "終了日 yyyy-mm-dd",
        "error.message": "エラーメッセージ: {message}",
        "error.stack_trace": "スタックトレース:",
        "error.type": "エラー種別: {type}",
        "error.unexpected": "予期しないエラーが発生しました:",
        "init.cache_policy": "キャッシュポリシー",
        "init.cancelled": "設定の初期化をキャンセルしました。",
        "init.created_config": "設定ファイルを作成しました: {path}",
        "init.footer.enter_value": "Enter 値を確定   Ctrl-B 戻る   Esc/Ctrl-C キャンセル",
        "init.footer.interval": "上下 移動   Space 選択   Enter 続行   Ctrl-B 戻る",
        "init.footer.language": "入力 検索   Space 切替   Enter 続行   Ctrl-B 戻る",
        "init.footer.language_suggestion": (
            "上下 移動   Space 候補を切替   Enter 続行"
        ),
        "init.footer.review": "Enter 設定を書き込み   Ctrl-B 戻る   Esc/Ctrl-C キャンセル",
        "init.footer.yes_no": "上下 移動   Space 選択   Y/N ショートカット   Ctrl-B 戻る",
        "init.language.instructions": "上下と Space で切替、Enter で続行します。",
        "init.language.search": "入力すると対応言語を検索します。",
        "init.language.suggestion_empty": "- 対応言語を検索するには入力してください。",
        "init.language.suggestion_instructions": (
            "上下と Space で候補言語を切り替えます。"
        ),
        "init.next": "次: python -m analyze_git_repo_loc run -i --config {path}",
        "init.provider.instructions": "上下と Space で切替、Enter で続行します。",
        "init.provider.updated": "プロバイダー選択を更新しました。",
        "init.select.instructions": "上下と Space で選択、Enter で続行します。",
        "init.title": "AnalyzeGitRepoLoc 初期設定ウィザード",
        "init.yes_no.instructions": "上下と Space で選択します。Y/N も使えます。",
        "output.finished": "完了",
        "warnings.title": "警告:",
    },
}


def resolve_language(locale_name: str | None) -> str:
    """Resolve a locale string to a supported language code."""
    if not locale_name:
        return "en"
    normalized = locale_name.strip().casefold()
    if normalized.startswith("ja") or normalized.startswith("japanese"):
        return "jp"
    return "en"


def current_language() -> str:
    """Return the language inferred from the current OS locale."""
    try:
        locale_name = locale.getlocale()[0]
    except (TypeError, ValueError):
        locale_name = None
    return resolve_language(locale_name)


def tr(key: str, *, language: str | None = None, **kwargs: Any) -> str:
    """Translate a message key and format it with keyword arguments."""
    selected_language = language if language in SUPPORTED_LANGUAGES else current_language()
    template = _MESSAGES.get(selected_language, {}).get(key)
    if template is None:
        template = _MESSAGES["en"].get(key, key)
    if not kwargs:
        return template
    return template.format(**kwargs)
