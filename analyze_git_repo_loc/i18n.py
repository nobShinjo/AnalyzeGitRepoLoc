"""Locale-based translations for user-facing text.

Description:
    Provides lightweight en/jp text lookup without adding gettext build steps.
    The active language is inferred from the operating system locale; Japanese
    locales use jp, and all other locales fall back to English.
Functions:
    resolve_language:
        Resolve a locale string to a supported language code.
    resolve_display_language:
        Resolve a CLI display language value to a supported language code.
    set_language_override:
        Set or clear the process-local display language override.
    current_language:
        Return the language inferred from the current OS locale.
    tr:
        Translate a message key with optional format arguments.
"""

from __future__ import annotations

import locale
from typing import Any

SUPPORTED_LANGUAGES = {"en", "jp"}
_LANGUAGE_OVERRIDE: str | None = None
_EN_NONE_TEXT = "(none)"
_JP_NONE_TEXT = "(なし)"
_EN_PROVIDERS_LABEL = "Providers"
_JP_PROVIDERS_LABEL = "プロバイダー"

_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "auth.device.code": "Code: {code}",
        "auth.device.open": "Open: {uri}",
        "auth.device.required": "OAuth Device Code login is required.",
        "auth.device.waiting": "Waiting for authorization in the browser...",
        "auth.enter_number": "Enter a number from the list.",
        "auth.gitlab_client_id_prompt": ("GitLab OAuth Application ID for this run: "),
        "auth.not_available": "{label} is not available.",
        "auth.provider_title": "{provider} authentication",
        "cli.config_help": "YAML configuration file path (default: config.yml).",
        "cli.description": "Analyze Git repositories and visualize code LOC.",
        "cli.display_language_help": (
            "Display language for this run (auto, en, or jp; default: auto)."
        ),
        "cli.doctor_help": "Validate YAML configuration before running analysis.",
        "cli.doctor_remote_help": "Also verify configured remote providers.",
        "cli.doctor_strict_help": "Treat warnings as doctor failures.",
        "doctor.error.date_format": "{name} must be YYYY-MM-DD.",
        "doctor.error.date_order": (
            "settings.since must be earlier than or equal to settings.until."
        ),
        "doctor.error.clone_protocol": (
            "interactive.defaults.clone_protocol must be 'https' or 'ssh'."
        ),
        "doctor.error.include_subpath_relative": (
            "{label}.include_subpath must be repository-relative."
        ),
        "doctor.error.include_subpath_traversal": (
            "{label}.include_subpath must not traverse outside the repository."
        ),
        "doctor.error.interval": (
            "settings.interval must be daily, weekly, or monthly."
        ),
        "doctor.error.interactive_providers_required": (
            "interactive.providers must be configured."
        ),
        "doctor.error.mapping": "YAML config '{config_key}' must be a mapping.",
        "doctor.error.provider_enabled_required": (
            "At least one interactive provider must be enabled."
        ),
        "doctor.error.remote_auth_required": (
            "{provider} environment token or CLI login is required for --remote diagnostics."
        ),
        "doctor.error.remote_branch_missing": "Remote branch '{branch}' was not found for repository '{repository}'.",
        "doctor.error.remote_provider_unsupported": (
            "Unsupported remote provider '{provider}'."
        ),
        "doctor.error.remote_repo_missing": (
            "Remote repository was not found in remote provider catalog: {path}"
        ),
        "doctor.error.repositories_list": "YAML config 'repositories' must be a list.",
        "doctor.error.repositories_non_empty": (
            "YAML config 'repositories' must be non-empty unless interactive is configured."
        ),
        "doctor.error.repositories_or_interactive_required": (
            "YAML config must define repositories or interactive providers."
        ),
        "doctor.error.repository_entry_type": "{label} must be a mapping or path string.",
        "doctor.error.repository_path_required": "{label}.path is required.",
        "doctor.error.secret_key": "Secret-like key must not be stored in YAML: {path}",
        "doctor.error.top_level_mapping": "YAML config must be a mapping at the top level.",
        "doctor.error.workers_int": "settings.workers must be an integer.",
        "doctor.error.workers_min": "settings.workers must be 1 or greater.",
        "doctor.report_success": "No doctor issues found.",
        "doctor.report_title": "Doctor diagnostics",
        "doctor.warning.exclude_dir_relative": (
            "{label}.exclude_dirs should be repository-relative: {path}"
        ),
        "doctor.warning.exclude_template_file_missing": (
            "Exclude template file does not exist: {path}"
        ),
        "doctor.warning.output_parent_missing": (
            "Output parent directory does not exist: {path}"
        ),
        "doctor.warning.remote_skipped": (
            "--remote skipped because interactive providers are not configured."
        ),
        "doctor.warning.repository_path_missing": "Repository path does not exist: {path}",
        "cli.init_config_help": (
            "YAML configuration file path to create (default: config.yml)."
        ),
        "cli.init_help": "Create an initial YAML configuration file interactively.",
        "cli.interactive_help": (
            "Review and adjust analysis settings interactively before running."
        ),
        "cli.interval_help": "Override aggregation interval for this run.",
        "cli.no_plot_show_help": (
            "Generate outputs without opening charts or reports."
        ),
        "cli.output_help": "Output path",
        "cli.run_help": (
            "Run analysis from a YAML configuration file, optionally interactively."
        ),
        "cli.since_help": "Override start date for this run (YYYY-MM-DD).",
        "cli.until_help": "Override end date for this run (YYYY-MM-DD).",
        "error.message": "Error message: {message}",
        "error.stack_trace": "Stack trace:",
        "error.type": "Error type: {type}",
        "error.unexpected": "An unexpected error occurred:",
        "exclude.summary.none": _EN_NONE_TEXT,
        "exclude.summary.paths": "Excluded paths",
        "exclude.summary.title": "Exclude templates:",
        "init.cache_policy": "Cache policy",
        "init.cancelled": "Config initialization cancelled.",
        "init.config_summary": "Config summary",
        "init.default_languages": "Default languages",
        "init.edit_value": "Edit the value below, then press Enter.",
        "init.initial_message": "Create an interactive-ready YAML config for AnalyzeGitRepoLoc.",
        "init.interval": "Analysis interval",
        "init.field.common_exclude_dirs": "Common exclude directories",
        "init.field.config_path": "Config file path",
        "init.field.gitlab_base_url": "Self-hosted GitLab base URL",
        "init.field.open_plots": "Open plots automatically [{suffix}]",
        "init.field.output": "Output directory",
        "init.field.overwrite": "Overwrite {path}? [{suffix}]",
        "init.field.since": "Start date YYYY-MM-DD",
        "init.field.until": "End date YYYY-MM-DD",
        "init.label.auto_display": "Auto display",
        "init.label.cache": "Cache",
        "init.label.config": "Config",
        "init.label.exclude_dirs": "Exclude dirs",
        "init.label.interval": "Interval",
        "init.label.languages": "Languages",
        "init.label.output": "Output",
        "init.label.period": "Period",
        "init.label.providers": _EN_PROVIDERS_LABEL,
        "init.value.all": "(all)",
        "init.value.blank": "(blank)",
        "init.value.none": _EN_NONE_TEXT,
        "init.created_config": "Created config: {path}",
        "init.footer.enter_value": "Enter accept value   Ctrl-B Back   Esc/Ctrl-C Cancel",
        "init.footer.interval": "Up/Down move   Space select   Enter continue   Ctrl-B Back",
        "init.footer.language": "Type search   Space toggle   Enter continue   Ctrl-B Back",
        "init.footer.language_suggestion": (
            "Up/Down move   Space toggle suggestion   Enter continue"
        ),
        "init.footer.provider": "Space toggle   Enter continue   Ctrl-B Back   Esc/Ctrl-C Cancel",
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
        "init.selected": "Selected: {value}",
        "init.provider.instructions": (
            "Use Up/Down, Space to toggle, Enter to continue."
        ),
        "init.provider.updated": "Provider selection updated.",
        "init.select.instructions": "Use Up/Down, Space to select, Enter to continue.",
        "init.step": "Step {current}/5 {name}",
        "init.step.analysis_defaults": "Analysis defaults",
        "init.step.config_file": "Config file",
        "init.step.providers": _EN_PROVIDERS_LABEL,
        "init.step.review": "Review",
        "init.step.runtime_behavior": "Runtime behavior",
        "init.suggestions": "Suggestions:",
        "init.title": "AnalyzeGitRepoLoc init wizard",
        "init.yes_no.instructions": (
            "Use Up/Down, Space to select. Y/N shortcut available."
        ),
        "output.cache": "Cache: {path}",
        "output.data": "Data: {path}",
        "output.finished": "Finished",
        "output.report": "Report: {path}",
        "output.repository_charts": "Repository charts: {path}",
        "output.run_data": "Run data: {path}",
        "output.summary": "Summary: {path}",
        "progress.charts.author_aggregate": "Charts: Author aggregate",
        "progress.charts.author_contribution": "Charts: Author contribution",
        "progress.charts.author_trend": "Charts: Author trend",
        "progress.charts.language_trend": "Charts: Language trend",
        "progress.charts.repository_trend": "Charts: Repository trend",
        "progress.forming_data": "Processing loc data",
        "progress.html_report": "Generating HTML report",
        "progress.remove_cache": "Remove cache files.",
        "progress.report_file_written": "Report file written",
        "progress.render_template": "Render template",
        "progress.repo.analyzing": "Analyzing repositories",
        "progress.repo.status.analyzing_commits": "analyzing commits",
        "progress.repo.status.done": "done",
        "progress.repo.status.getting_commits": "getting commits",
        "progress.repo.status.queued": "queued",
        "progress.saving_data": "Saving analyzed data",
        "progress.trend_chart": "Generating trend chart",
        "run.finish": "FINISH",
        "run.section.excluded_directories": "Excluded directories: {paths}",
        "run.section.forming_dataframe": "Forming dataframe type data.",
        "run.section.generate_charts": "Generate charts.",
        "run.section.generate_html_report": "Generate HTML report.",
        "run.section.repository_analysis": (
            "Analysis of LOC in git repository: {repository} ({branch})"
        ),
        "run.section.save_data": "Save the analyzed data.",
        "tui.action": "Action",
        "tui.analysis_scope": "Analysis scope",
        "tui.auto_display": "Auto display: {value}",
        "tui.auto_display_prompt": "Automatically show charts/reports",
        "tui.authors": "Authors: {value}",
        "tui.author_filter": "Author filter",
        "tui.branch_selection": "Branch selection",
        "tui.bulk_branch": "Bulk branch override (blank/default keeps repository defaults)",
        "tui.cache": "Cache: {policy}",
        "tui.cache_policy_prompt": "Cache policy (use/update/clear)",
        "tui.cache_policy_error": "cache policy must be use, update, or clear.",
        "tui.category.analysis": "Analysis Scope",
        "tui.category.done": "Done",
        "tui.category.output": "Output / Cache / Display",
        "tui.category.paths": "Path Rules",
        "tui.category.providers": _EN_PROVIDERS_LABEL,
        "tui.category.repositories": "Repositories / Branches",
        "tui.choose_action": "Choose Enter, e, d, s, or c.",
        "tui.choose_category": "Choose a category number or name.",
        "tui.edit_settings": "Edit Settings",
        "tui.edit_individual_repos": "Edit individual repositories",
        "tui.edit_per_repo_paths": "Edit per-repository path rules",
        "tui.enter_yes_no": "Enter y or n.",
        "tui.final_actions": "[Enter] Run   e Edit   d Details   s Save+Run   c Cancel",
        "tui.global_excludes": "Global excludes: {value} (applied only when present)",
        "tui.global_excludes_prompt": "Global exclude paths",
        "tui.include_subpath_prompt": "{repo} include subpath",
        "tui.interval": "Interval: {value}",
        "tui.interval_error": "interval must be daily, weekly, or monthly.",
        "tui.interval_prompt": "Interval (daily/weekly/monthly)",
        "tui.languages": "Languages: {value}",
        "tui.language_filter": "Language filter",
        "tui.none": _EN_NONE_TEXT,
        "tui.off": "off",
        "tui.on": "on",
        "tui.output_cache_display": "Output / Cache / Display",
        "tui.output_directory": "Output directory",
        "tui.output_line": "Output: {path}",
        "tui.path_rules": "Path rules",
        "tui.period": "Period: {since} -> {until}",
        "tui.provider_restart": "Provider changes require restarting the interactive run.",
        "tui.provider_selection": "Provider selection",
        "tui.providers": "Providers: {value}",
        "tui.provider_required": "At least one provider must be selected.",
        "tui.quick_review": "Quick Review",
        "tui.recommended_excludes": "Recommended excludes: {value}",
        "tui.recommended_languages": "Recommended languages: {value} ({source})",
        "tui.repo_branch_prompt": "{repo} branch",
        "tui.repo_excludes_prompt": "{repo} exclude paths",
        "tui.repo_extra_excludes_prompt": "{repo} extra exclude paths",
        "tui.repositories": "Repositories:",
        "tui.repository_count": "Repositories: {count}",
        "tui.select_category": "Select category",
        "tui.self_hosted_gitlab_base_url": "Self-hosted GitLab base URL",
        "tui.self_hosted_gitlab_base_url_required": "Self-hosted GitLab base URL is required.",
        "tui.since_prompt": "Since yyyy-mm-dd",
        "tui.suggestions": "Suggestions: {value} ({source})",
        "tui.until_prompt": "Until yyyy-mm-dd",
        "tui.use_provider": "Use {label}",
        "tui.workers_error": "workers must be 1 or higher.",
        "tui.workers_prompt": "Workers/concurrency",
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
        "cli.display_language_help": (
            "この実行の表示言語 (auto, en, jp / 既定: auto)。"
        ),
        "cli.doctor_help": "解析前に YAML 設定を検査します。",
        "cli.doctor_remote_help": "設定済みリモートプロバイダーも検査します。",
        "cli.doctor_strict_help": "警告も doctor の失敗として扱います。",
        "doctor.error.date_format": "{name} は YYYY-MM-DD 形式で指定してください。",
        "doctor.error.date_order": "settings.since は settings.until 以下である必要があります。",
        "doctor.error.clone_protocol": (
            "interactive.defaults.clone_protocol は 'https' または 'ssh' にしてください。"
        ),
        "doctor.error.include_subpath_relative": (
            "{label}.include_subpath はリポジトリ相対パスで指定してください。"
        ),
        "doctor.error.include_subpath_traversal": (
            "{label}.include_subpath はリポジトリ外を指してはいけません。"
        ),
        "doctor.error.interval": "settings.interval は daily, weekly, monthly のいずれかにしてください。",
        "doctor.error.interactive_providers_required": (
            "interactive.providers を設定してください。"
        ),
        "doctor.error.mapping": "YAML 設定の '{config_key}' は mapping である必要があります。",
        "doctor.error.provider_enabled_required": (
            "少なくとも 1 つの interactive provider を有効にしてください。"
        ),
        "doctor.error.remote_auth_required": (
            "{provider} の環境変数トークン、または CLI ログインが --remote 診断に必要です。"
        ),
        "doctor.error.remote_branch_missing": (
            "リモートブランチ '{branch}' がリポジトリ '{repository}' に存在しません。"
        ),
        "doctor.error.remote_provider_unsupported": (
            "未対応のリモートプロバイダーです: '{provider}'。"
        ),
        "doctor.error.remote_repo_missing": (
            "リモートプロバイダーのカタログに対象リポジトリが見つかりません: {path}"
        ),
        "doctor.error.repositories_list": "YAML 設定の 'repositories' は list である必要があります。",
        "doctor.error.repositories_non_empty": (
            "interactive 未設定時、YAML 設定の 'repositories' は空にできません。"
        ),
        "doctor.error.repositories_or_interactive_required": (
            "YAML 設定には repositories または interactive providers が必要です。"
        ),
        "doctor.error.repository_entry_type": (
            "{label} は mapping または path 文字列である必要があります。"
        ),
        "doctor.error.repository_path_required": "{label}.path は必須です。",
        "doctor.error.secret_key": "YAML に秘密情報らしきキーを保存してはいけません: {path}",
        "doctor.error.top_level_mapping": "YAML 設定のトップレベルは mapping である必要があります。",
        "doctor.error.workers_int": "settings.workers は整数である必要があります。",
        "doctor.error.workers_min": "settings.workers は 1 以上である必要があります。",
        "doctor.report_success": "Doctor の問題は見つかりませんでした。",
        "doctor.report_title": "Doctor 診断",
        "doctor.warning.exclude_dir_relative": (
            "{label}.exclude_dirs はリポジトリ相対パスにしてください: {path}"
        ),
        "doctor.warning.exclude_template_file_missing": (
            "exclude template file が存在しません: {path}"
        ),
        "doctor.warning.output_parent_missing": (
            "出力先の親ディレクトリが存在しません: {path}"
        ),
        "doctor.warning.remote_skipped": (
            "interactive providers が未設定のため --remote をスキップしました。"
        ),
        "doctor.warning.repository_path_missing": "リポジトリパスが存在しません: {path}",
        "cli.init_config_help": (
            "作成する YAML 設定ファイルのパス (既定: config.yml)。"
        ),
        "cli.init_help": "初期 YAML 設定ファイルを対話形式で作成します。",
        "cli.interactive_help": ("解析前に対話形式で設定を確認・調整します。"),
        "cli.interval_help": "この実行だけ集計間隔を上書きします。",
        "cli.no_plot_show_help": (
            "チャートやレポートを自動表示せず、出力だけ生成します。"
        ),
        "cli.output_help": "出力パス",
        "cli.run_help": "YAML 設定ファイルから解析を実行します。対話実行も可能です。",
        "cli.since_help": "この実行だけ開始日を上書きします (YYYY-MM-DD)。",
        "cli.until_help": "この実行だけ終了日を上書きします (YYYY-MM-DD)。",
        "error.message": "エラーメッセージ: {message}",
        "error.stack_trace": "スタックトレース:",
        "error.type": "エラー種別: {type}",
        "error.unexpected": "予期しないエラーが発生しました:",
        "exclude.summary.none": _JP_NONE_TEXT,
        "exclude.summary.paths": "除外パス",
        "exclude.summary.title": "除外テンプレート:",
        "init.cache_policy": "キャッシュポリシー",
        "init.cancelled": "設定の初期化をキャンセルしました。",
        "init.config_summary": "設定サマリー",
        "init.default_languages": "既定の言語",
        "init.edit_value": "下の値を編集して Enter を押してください。",
        "init.initial_message": "対話実行に使える YAML 設定を作成します。",
        "init.interval": "集計間隔",
        "init.field.common_exclude_dirs": "共通除外ディレクトリ",
        "init.field.config_path": "設定ファイルパス",
        "init.field.gitlab_base_url": "セルフホスト GitLab のベース URL",
        "init.field.open_plots": "プロットを自動表示 [{suffix}]",
        "init.field.output": "出力ディレクトリ",
        "init.field.overwrite": "{path} を上書きしますか? [{suffix}]",
        "init.field.since": "開始日 YYYY-MM-DD",
        "init.field.until": "終了日 YYYY-MM-DD",
        "init.label.auto_display": "自動表示",
        "init.label.cache": "キャッシュ",
        "init.label.config": "設定",
        "init.label.exclude_dirs": "除外ディレクトリ",
        "init.label.interval": "集計間隔",
        "init.label.languages": "言語",
        "init.label.output": "出力",
        "init.label.period": "期間",
        "init.label.providers": _JP_PROVIDERS_LABEL,
        "init.value.all": "(すべて)",
        "init.value.blank": "(空)",
        "init.value.none": _JP_NONE_TEXT,
        "init.created_config": "設定ファイルを作成しました: {path}",
        "init.footer.enter_value": "Enter 値を確定   Ctrl-B 戻る   Esc/Ctrl-C キャンセル",
        "init.footer.interval": "上下 移動   Space 選択   Enter 続行   Ctrl-B 戻る",
        "init.footer.language": "入力 検索   Space 切替   Enter 続行   Ctrl-B 戻る",
        "init.footer.language_suggestion": (
            "上下 移動   Space 候補を切替   Enter 続行"
        ),
        "init.footer.provider": "Space 切替   Enter 続行   Ctrl-B 戻る   Esc/Ctrl-C キャンセル",
        "init.footer.review": "Enter 設定を書き込み   Ctrl-B 戻る   Esc/Ctrl-C キャンセル",
        "init.footer.yes_no": "上下 移動   Space 選択   Y/N ショートカット   Ctrl-B 戻る",
        "init.language.instructions": "上下と Space で切替、Enter で続行します。",
        "init.language.search": "入力すると対応言語を検索します。",
        "init.language.suggestion_empty": "- 対応言語を検索するには入力してください。",
        "init.language.suggestion_instructions": (
            "上下と Space で候補言語を切り替えます。"
        ),
        "init.next": "次: python -m analyze_git_repo_loc run -i --config {path}",
        "init.selected": "選択中: {value}",
        "init.provider.instructions": "上下と Space で切替、Enter で続行します。",
        "init.provider.updated": "プロバイダー選択を更新しました。",
        "init.select.instructions": "上下と Space で選択、Enter で続行します。",
        "init.step": "ステップ {current}/5 {name}",
        "init.step.analysis_defaults": "解析既定値",
        "init.step.config_file": "設定ファイル",
        "init.step.providers": _JP_PROVIDERS_LABEL,
        "init.step.review": "確認",
        "init.step.runtime_behavior": "実行時の動作",
        "init.suggestions": "候補:",
        "init.title": "AnalyzeGitRepoLoc 初期設定ウィザード",
        "init.yes_no.instructions": "上下と Space で選択します。Y/N も使えます。",
        "output.cache": "キャッシュ: {path}",
        "output.data": "データ: {path}",
        "output.finished": "完了",
        "output.report": "レポート: {path}",
        "output.repository_charts": "リポジトリ別チャート: {path}",
        "output.run_data": "実行データ: {path}",
        "output.summary": "サマリー: {path}",
        "progress.charts.author_aggregate": "チャート: Author 集計",
        "progress.charts.author_contribution": "チャート: Author contribution",
        "progress.charts.author_trend": "チャート: Author トレンド",
        "progress.charts.language_trend": "チャート: Language トレンド",
        "progress.charts.repository_trend": "チャート: Repository トレンド",
        "progress.forming_data": "LOC データ処理中",
        "progress.html_report": "HTML レポート生成中",
        "progress.remove_cache": "キャッシュファイルを削除します。",
        "progress.report_file_written": "レポートファイル書き込み完了",
        "progress.render_template": "テンプレート描画",
        "progress.repo.analyzing": "リポジトリ解析中",
        "progress.repo.status.analyzing_commits": "commit 解析中",
        "progress.repo.status.done": "完了",
        "progress.repo.status.getting_commits": "commit 取得中",
        "progress.repo.status.queued": "待機中",
        "progress.saving_data": "解析データ保存中",
        "progress.trend_chart": "トレンドチャート生成中",
        "run.finish": "完了",
        "run.section.excluded_directories": "除外ディレクトリ: {paths}",
        "run.section.forming_dataframe": "DataFrame 形式のデータを整形します。",
        "run.section.generate_charts": "チャートを生成します。",
        "run.section.generate_html_report": "HTML レポートを生成します。",
        "run.section.repository_analysis": (
            "Git リポジトリの LOC を解析します: {repository} ({branch})"
        ),
        "run.section.save_data": "解析データを保存します。",
        "tui.action": "操作",
        "tui.analysis_scope": "解析範囲",
        "tui.auto_display": "自動表示: {value}",
        "tui.auto_display_prompt": "グラフ/レポートを自動表示する",
        "tui.authors": "作成者: {value}",
        "tui.author_filter": "作成者フィルター",
        "tui.branch_selection": "ブランチ選択",
        "tui.bulk_branch": "一括ブランチ上書き (空/default はリポジトリ既定を維持)",
        "tui.cache": "キャッシュ: {policy}",
        "tui.cache_policy_prompt": "キャッシュポリシー (use/update/clear)",
        "tui.cache_policy_error": "cache policy は use, update, clear のいずれかにしてください。",
        "tui.category.analysis": "解析範囲",
        "tui.category.done": "完了",
        "tui.category.output": "出力 / キャッシュ / 表示",
        "tui.category.paths": "パスルール",
        "tui.category.providers": _JP_PROVIDERS_LABEL,
        "tui.category.repositories": "リポジトリ / ブランチ",
        "tui.choose_action": "Enter、e、d、s、c のいずれかを選んでください。",
        "tui.choose_category": "カテゴリ番号または名前を入力してください。",
        "tui.edit_settings": "設定編集",
        "tui.edit_individual_repos": "リポジトリごとに編集する",
        "tui.edit_per_repo_paths": "リポジトリごとのパスルールを編集する",
        "tui.enter_yes_no": "y または n を入力してください。",
        "tui.final_actions": "[Enter] 実行   e 編集   d 詳細   s 保存して実行   c キャンセル",
        "tui.global_excludes": "グローバル除外: {value} (存在する場合のみ適用)",
        "tui.global_excludes_prompt": "グローバル除外パス",
        "tui.include_subpath_prompt": "{repo} 解析サブパス",
        "tui.interval": "集計間隔: {value}",
        "tui.interval_error": "interval は daily, weekly, monthly のいずれかにしてください。",
        "tui.interval_prompt": "集計間隔 (daily/weekly/monthly)",
        "tui.languages": "言語: {value}",
        "tui.language_filter": "言語フィルター",
        "tui.none": _JP_NONE_TEXT,
        "tui.off": "オフ",
        "tui.on": "オン",
        "tui.output_cache_display": "出力 / キャッシュ / 表示",
        "tui.output_directory": "出力ディレクトリ",
        "tui.output_line": "出力: {path}",
        "tui.path_rules": "パスルール",
        "tui.period": "期間: {since} -> {until}",
        "tui.provider_restart": "プロバイダー変更には対話実行の再起動が必要です。",
        "tui.provider_selection": "プロバイダー選択",
        "tui.providers": "プロバイダー: {value}",
        "tui.provider_required": "少なくとも 1 つのプロバイダーを選択してください。",
        "tui.quick_review": "クイック確認",
        "tui.recommended_excludes": "推奨除外: {value}",
        "tui.recommended_languages": "推奨言語: {value} ({source})",
        "tui.repo_branch_prompt": "{repo} ブランチ",
        "tui.repo_excludes_prompt": "{repo} 除外パス",
        "tui.repo_extra_excludes_prompt": "{repo} 追加除外パス",
        "tui.repositories": "リポジトリ:",
        "tui.repository_count": "リポジトリ: {count}",
        "tui.select_category": "カテゴリ選択",
        "tui.self_hosted_gitlab_base_url": "セルフホスト GitLab のベース URL",
        "tui.self_hosted_gitlab_base_url_required": "セルフホスト GitLab のベース URL が必要です。",
        "tui.since_prompt": "開始日 yyyy-mm-dd",
        "tui.suggestions": "候補: {value} ({source})",
        "tui.until_prompt": "終了日 yyyy-mm-dd",
        "tui.use_provider": "{label} を使う",
        "tui.workers_error": "workers は 1 以上にしてください。",
        "tui.workers_prompt": "並列数",
        "warnings.title": "警告:",
    },
}


def resolve_language(locale_name: str | None) -> str:
    """Resolve a locale string to a supported language code."""
    if not locale_name:
        return "en"
    normalized = locale_name.strip().casefold()
    if normalized.startswith(("ja", "japanese")):
        return "jp"
    return "en"


def resolve_display_language(value: str | None) -> str | None:
    """Resolve a display language option to a supported override code."""
    if value is None:
        return None
    normalized = value.strip().casefold()
    if not normalized or normalized == "auto":
        return None
    if normalized in {"en", "english"}:
        return "en"
    if normalized in {"jp", "ja", "japanese"}:
        return "jp"
    raise ValueError("display language must be auto, en, or jp.")


def set_language_override(language: str | None) -> None:
    """Set or clear the process-local display language override."""
    global _LANGUAGE_OVERRIDE  # pylint: disable=global-statement
    _LANGUAGE_OVERRIDE = language if language in SUPPORTED_LANGUAGES else None


def current_language() -> str:
    """Return the language inferred from the current OS locale."""
    if _LANGUAGE_OVERRIDE is not None:
        return _LANGUAGE_OVERRIDE
    try:
        locale_name = locale.getlocale()[0]
    except TypeError, ValueError:
        locale_name = None
    return resolve_language(locale_name)


def tr(key: str, *, language: str | None = None, **kwargs: Any) -> str:
    """Translate a message key and format it with keyword arguments."""
    selected_language = (
        language if language in SUPPORTED_LANGUAGES else current_language()
    )
    template = _MESSAGES.get(selected_language, {}).get(key)
    if template is None:
        template = _MESSAGES["en"].get(key, key)
    if not kwargs:
        return template
    return template.format(**kwargs)
