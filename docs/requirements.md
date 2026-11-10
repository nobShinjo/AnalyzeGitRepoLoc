# AnalyzeGitRepoLOC 現行仕様

## 目的と範囲

Git の非マージコミットを解析し、言語・作者・リポジトリ別の NLOC
（コメント・空行を除くコード行数の増減）を CSV、HTML、Markdown に出力する CLI。
Python 3.14 以上と Git を必要とする。GUI アプリや Web API サーバは提供しない。

この文書を現行仕様の入口とする。開発ルールは [AGENTS.md](../AGENTS.md)、
今後の作業計画は [plans/](plans/)、過去の作業記録は [tasks/](../tasks/README.md) を参照する。

## 起動と CLI

`uv sync --frozen` で `.venv` にプロジェクトと依存をインストールする。
`uv run analyze-git-repo-loc` と `uv run -m analyze_git_repo_loc` を同じ引数で起動できる。
トップレベルの `--version` はパッケージの版（v3.3.0 では `3.3.0`）を表示して終了する。

```shell
uv run analyze-git-repo-loc --version
uv run analyze-git-repo-loc --help
uv run analyze-git-repo-loc init [--config config.yml]
uv run analyze-git-repo-loc doctor [--config config.yml] [--remote] [--strict]
uv run analyze-git-repo-loc run [--config config.yml] [-i] [-o OUTPUT] \
  [--since YYYY-MM-DD] [--until YYYY-MM-DD] \
  [--interval {daily,weekly,monthly}] [--no-plot-show]
```

- `init`: 対話形式で初期 YAML を生成する。既存ファイルの上書きは確認を必要とする。
  新規ファイルには認証情報やリポジトリ選択を保存しない。
- `doctor`: YAML 構造、設定値、ローカルリポジトリ、出力先、秘密情報らしいキーを診断する。
  `--remote` ではプロバイダー API も確認し、`--strict` では警告も失敗として扱う。
- `run`: YAML に基づく非対話解析。`-i` / `--interactive` で対話フローに入る。
  CLI の出力先・期間・集計間隔・表示抑止は YAML より優先する。
- `-L` / `--display-language {auto,en,jp}`: トップレベルと各サブコマンドで指定できる。
  `auto` は OS のロケールに従う。
- `repo_paths`、`--workers`、`--lang`、`--author-name`、`--exclude-dirs`、
  `--clear-cache` は公開 CLI 引数ではない。対応する設定は YAML で指定する。

## YAML と対話操作

- `repositories` にローカルパスまたは Git URL の `path` と任意の `branch` を列挙する。
  ブランチ省略時は `main`。リポジトリ単位の `exclude_dirs`、`include_subpath` に対応する。
- `settings` で `output`（既定 `./out`）、`interval`（既定 `monthly`）、
  `since`、`until`、`lang`、`author_name`、`exclude_dirs`、`workers`、
  `clear_cache`、`no_plot_show` を指定する。
- 除外テンプレートは `exclude_template_mode`、`exclude_template_names`、
  `exclude_template_files` で選択する。詳細と設定例は [README](../README.ja.md) を参照する。
- 期間は片側だけの指定も可能。開始日が終了日より後ならエラーとする。
  空の任意フィルターは未指定として扱う。
- `run -i` は GitHub/GitLab の一覧から検索・複数選択し、条件を確認して通常解析へ進む。
  Quick Review は実行、編集、詳細、保存のみ、保存して実行、再選択、キャンセルを提供する。
  詳細表示と保存のみの後は Quick Review に戻る。
- 認証情報は YAML に保存しない。環境変数、既存 `gh` / `glab` ログイン、
  Device Code、一時トークンを対話フローで扱う。

## Git 解析、並列実行、キャッシュ

- 非マージコミットから `Datetime`、`Repository`、`Branch`、`Commit_hash`、
  `Author`、`Language`、`NLOC_Added`、`NLOC_Deleted`、`NLOC` を抽出する。
- 拡張子マッピングで言語を判定する。未知の言語を除外し、コメントと空行は NLOC に含めない。
- 期間・言語・作者・除外ディレクトリの条件を適用し、日・週・月単位で集計する。
- リポジトリ並列数は `settings.workers` で指定する。未指定時は CPU 数と対象数から決定し、
  最低 1 とする。集計結果のリポジトリ順序は入力順に保つ。
- 同じローカル Git root または同じリモートキャッシュを複数エントリが使う場合、
  checkout や `.git/config.lock` の競合を避けるため、その実行は 1 worker に切り替える。
- SSH URL は SSH 認証を使い、HTTPS では GitHub/GitLab のトークンを利用できる。
  clone・fetch は非対話で実行し、リモート clone を出力先の `.cache/remote-repos/` に再利用する。
  認証処理とリモートリポジトリ操作はそれぞれ専用モジュールで扱う。
- コミット解析キャッシュは `<output>/.cache/<repository>/commit_data.pkl` に保存する。
  メタデータでリポジトリ・ブランチ・期間・フィルターの互換性を確認し、HEAD が一致すれば
  走査を省略する。HEAD が更新された場合は未解析コミットを処理する。
  `settings.clear_cache` が有効なら再計算する。
- 同じリポジトリ状態と条件では解析結果を再現できること。出力作成失敗や回復不能エラーは
  エラーメッセージを出して終了する。

## 出力と進捗

リポジトリ別の `<output>/<repository>/` に次を出力する。

- `loc_data.csv`
- `language_trends.csv`、`language_trend_data.csv`、`language_summary_data.csv`、`language_chart.html`
- `author_trends.csv`、`author_trend_data.csv`、`author_summary_data.csv`、`author_chart.html`

実行ごとの `<output>/YYYYMMDDHHMMSS/` に次を出力する。

- `summary.md`、`repo_list.txt`
- `language_analysis.csv`、`author_analysis.csv`、`repository_trend_analysis.csv`
- `report.html` とローカルの `assets/`
- 複数リポジトリ時は `repository_chart.html`、`author_chart.html`、
  `author_contribution_contribution_chart.html` と対応する集計 CSV

単一リポジトリでは言語・作者チャートを、複数では統合レポートを自動表示する。
`--no-plot-show` なら成果物だけを生成し、自動表示を抑止する。
リポジトリ・コミット解析、チャート生成、HTML 生成の各段階で進捗を通知する。
チャートの親進捗は 5 ステップ、HTML のフィルターデータ整形はバッチごとに更新する。

## HTML レポート

- 全体概要と各リポジトリのタブを備え、タブの内容・チャートを遅延描画する。
- 言語・作者・リポジトリを絞り込むタグと検索、全選択への復帰を提供する。
  タグは NLOC の降順で、初期状態はすべて有効。全選択時のタグクリックは単独選択、
  無効タグのクリックは再有効化、`x` は無効化とする。
- フィルターはタブごとに管理し、テーブルだけを更新する。
  チャートはタブの全データから描画し、タグ操作では変更しない。
- 言語テーブルの合計行、固定されたタイトル・タブ、フィルター状態の表示を提供する。
- 埋め込みフィルター行は `interval`、`repository`、`author`、`language`、
  `nloc_added`、`nloc_deleted`、`nloc` を持つ。

## 依存管理と仕様の整理

依存の正本は `pyproject.toml` と `uv.lock`。ライセンス一覧は
`uv run pip-licenses --format=markdown --ignore-packages analyze-git-repo-loc
--output-file=3rdPartyLicenses.md` で生成し、先頭に Markdown のレベル 1 見出しを追加する。
`uv run pytest` で回帰テストを実行する。

旧仕様からは解析・出力・キャッシュ・認証・並列処理・レポートの現行契約を移管した。
旧 CLI の位置引数、廃止済みオプション、requirements.txt を使う手順は引き継がない。
期間差分比較（基準期間と差分表・チャート）は現行 CLI に存在せず、実装済み機能や
今回の残作業として扱わない。旧チェックリストの完了印だけで実装状態を判断しない。
