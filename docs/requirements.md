# AnalyzeGitRepoLOC 要件定義（開発者向け）

## 概要

Git リポジトリのコミット履歴から LOC（実質的なコード行数）を解析し、言語・作者・リポジトリ別に集計して CSV と Plotly の HTML チャートとして出力する CLI ツール。

## スコープ

- 対象: ローカルの Git リポジトリ、および URL 指定の Git リポジトリ
- 対象外: GUI、Web API サーバ、コードフォーマット・静的解析

## 機能要件

- FR-01: `python -m analyze_git_repo_loc` で CLI を起動できること。
- FR-02: `repo_paths` には次を受け付けること。
  - カンマ区切りのリポジトリパス/URL リスト
  - 1 行 1 リポジトリのテキストファイル
- FR-03: 各リポジトリ指定は `repo_path#branch` 形式でブランチを指定でき、未指定の場合は `main` を使用すること。
- FR-04: 解析対象は Git のコミット履歴（マージコミット除外）であり、以下の情報を抽出すること。
  - 日時、リポジトリ名、ブランチ、コミットハッシュ、作者、言語、追加行数、削除行数、差分（NLOC）
- FR-05: LOC 解析は、対象言語の拡張子により言語を判定し、コメント行・空行を除外すること。
- FR-06: フィルタリング機能を提供すること。
  - 期間（`--since`, `--until`）
  - 集計間隔（`daily`, `weekly`, `monthly`）
  - 言語フィルタ（`--lang`）
  - 作者フィルタ（`--author-name`）
  - 除外ディレクトリ（`--exclude-dirs` または `repo_path#branch,exclude1,exclude2`）
- FR-07: 解析結果は出力ディレクトリ（既定: `./out`）へ CSV で保存すること。
- FR-08: 可視化用の Plotly HTML チャートを生成し、オプションで表示を抑止できること（`--no-plot-show`）。
- FR-09: 複数リポジトリの同時解析に対応すること。
- FR-10: 解析済みコミットはキャッシュを保存し、`--clear-cache` で削除できること。
- FR-11: 進捗はコンソールに表示し、致命的エラーはメッセージを出して終了すること。

## 非機能要件

- NFR-01: Python 3.14 以上で動作すること。
- NFR-02: 依存関係は `pyproject.toml` と `uv.lock` に基づく（例: pandas, plotly, pydriller, gitpython, tqdm, colorama）。
- NFR-03: 大規模リポジトリでも実行可能なよう、コミット解析は CPU コア数を用いた並列処理を活用すること。
- NFR-04: 同一入力に対して再実行時の結果が再現可能であること（同一リポジトリ状態・同一期間）。
- NFR-05: 言語判定は拡張子マッピングに従い、未知の言語はスキップすること。
- NFR-06: 出力ディレクトリ作成やファイル書き込みに失敗した場合はエラーとして終了すること。

## 追加機能要件（案）

- FR-12: YAML 設定ファイルから解析設定を読み込めること（CLI 引数で上書き可能）。
- FR-13: 単一 HTML レポートを生成し、タブ切り替えで全体概要と各リポジトリ詳細を閲覧できること。
- FR-14: レポート内でインタラクティブなフィルタリング（言語/作者/リポジトリ）が可能であること。
- FR-15: 期間差分比較を行い、対象期間と基準期間の差分表・差分チャートを出力できること。
- FR-16: リモートリポジトリ（Git URL）を解析対象にできること。
- FR-17: リモート認証は SSH 鍵を優先し、必要に応じて GitHub/GitLab トークン（環境変数）に対応すること。
- FR-18: 解析結果の summary を Markdown で出力できること。
- FR-19: 解析時間短縮のためのキャッシュ再利用・差分解析を提供できること。
- FR-20: YAML で複数リポジトリと個別設定（ブランチ・除外ディレクトリ等）を定義できること。

## 追加非機能要件（案）

- NFR-07: 依存管理は uv を採用し、`pyproject.toml` と `uv.lock` による再現性を確保すること。
- NFR-08: リモートリポジトリのクローン先は再利用可能なキャッシュディレクトリを持つこと。
- NFR-09: 単一 HTML レポートは大量データでも操作性を損なわないよう、タブ単位で描画/読み込みを最適化すること。

## API

### CLI

```bash
python -m analyze_git_repo_loc [repo_paths] \
  -o ./out \
  --since YYYY-MM-DD \
  --until YYYY-MM-DD \
  --interval {daily,weekly,monthly} \
  --lang L1,L2,... \
  --author-name A1,A2,... \
  --exclude-dirs dir1,dir2 \
  --clear-cache \
  --no-plot-show
```

### 引数仕様

- `repo_paths`:
  - カンマ区切り: `path1#branch,path2#branch`
  - ファイル指定: 1 行 1 リポジトリ。各行は `repo_path#branch,exclude1,exclude2` 形式。
- `--since` / `--until`: ISO 形式の日付（`YYYY-MM-DD`）。
- `--interval`: 集計単位（`daily` / `weekly` / `monthly`）。
- `--lang`: 対象言語（`LANGUAGES.md` のキーに準拠）。
- `--author-name`: 作者名フィルタ（複数可）。
- `--exclude-dirs`: リポジトリ配下の相対パスで除外ディレクトリを指定。

### 出力仕様

既定出力ディレクトリは `./out`。主な生成物は以下。

- 各リポジトリ配下
  - `loc_data.csv`
  - `language_trends.csv`, `author_trends.csv`
  - `language_trend_data.csv`, `language_summary_data.csv`, `language_chart.html`
  - `author_trend_data.csv`, `author_summary_data.csv`, `author_chart.html`
- 実行時刻のサブディレクトリ（例: `./out/20260101120000/`）
  - `language_analysis.csv`, `author_analysis.csv`, `repository_trend_analysis.csv`
  - `repo_list.txt`
  - `repository_trend_data.csv`, `repository_summary_data.csv`, `repository_chart.html`
  - `author_trend_data.csv`, `author_summary_data.csv`, `author_chart.html`
  - `author_contribution_summary_data.csv`, `author_contribution_contribution_chart.html`
- キャッシュ
  - `./out/.cache/<repo>/commit_data.pkl`
