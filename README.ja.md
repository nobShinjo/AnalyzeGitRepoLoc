# AnalyzeGitRepoLOC

[English README](./README.md)

## 概要

Git リポジトリを解析し、コード行数 (LOC) を可視化します。

CLI の表示言語は OS のロケールを参照して自動で切り替わります。
日本語環境では日本語、それ以外では英語を使用します。

## リリースノート

[CHANGELOG](./CHANGELOG.md)

## 要件

1. このリポジトリを clone します。
2. Python 3.14 以上を用意します。
3. 依存関係を同期します。

```shell
uv sync --active
```

## 使い方

### コマンドライン

CLI は次の入口を中心にしています。

```shell
python -m analyze_git_repo_loc init [--config config.yml]
python -m analyze_git_repo_loc doctor [--config config.yml] [--remote] [--strict]
python -m analyze_git_repo_loc run [--config config.yml] [options]
python -m analyze_git_repo_loc run -i [--config config.yml]
```

- `init`: 対話形式で初期 YAML 設定を作成します。
- `doctor`: 解析前に YAML 設定、出力先、リポジトリ、認証設定を診断します。
- `run -i`: 解析前にリポジトリ、ブランチ、フィルター、出力、キャッシュを確認して実行します。
- `run`: YAML 設定から非対話のバッチ解析を実行します。

直接 `repo_paths` をコマンドライン引数に渡す入口は廃止されています。
リポジトリは YAML に定義するか、`run -i` で選択して設定を保存してください。

### リモート認証

CLI はリモートリポジトリに対して SSH キーを優先します。
SSH が使えない場合は、GitHub または GitLab の HTTPS トークン認証に
フォールバックできます。

実行前に次の環境変数を設定できます。

- `GITHUB_TOKEN`: GitHub の HTTPS 認証用 personal access token。
- `GITLAB_TOKEN`: GitLab の HTTPS 認証用 personal access token。

`run -i` では、環境変数トークン、既存の `gh` / `glab` ログイン、
OAuth Device Code、実行時だけ入力する one-time token を選べます。
認証情報は YAML、ファイル、keyring には保存しません。

## 例

### 初期設定を作成する

```shell
python -m analyze_git_repo_loc init
```

`init` は対話形式で `config.yml` を作成します。
既存ファイルがある場合は、既存値を初期表示し、上書き確認を行います。
解析間隔、キャッシュポリシー、表示設定は選択式です。
既定言語はチェックボックス形式で選択でき、入力に応じて対応言語候補を表示します。
既存の `repositories` と、`repositories:` 配下にコメントアウトして残した
リポジトリ候補は保持されます。

作成後は次のように対話実行できます。

```shell
python -m analyze_git_repo_loc run -i
```

### 対話形式で解析する

```shell
python -m analyze_git_repo_loc run -i --config ./config.yml
```

`run -i` は有効な GitHub/GitLab プロバイダーからリポジトリを取得し、
検索と複数選択を行ったうえで、通常の解析パイプラインを実行します。

プロバイダーが 1 つだけ設定され、`GITHUB_TOKEN` / `GITLAB_TOKEN` または
既存の `gh` / `glab` ログインが利用できる場合は、Quick Review から開始します。
Enter で実行、`e` で編集、`d` で詳細、`s` で保存のみ、`x` で保存して実行、
`i` でリポジトリ選択へ戻り、`c` でキャンセルします。詳細表示後と保存のみの
操作後は、Quick Review の最終確認メニューへ戻ります。

### 設定を診断する

```shell
python -m analyze_git_repo_loc doctor --config ./config.yml
```

`doctor` は YAML 構造、解析設定、リポジトリパス、出力パス、
シークレットらしいキーを軽量に確認します。`--remote` を追加すると
GitHub/GitLab プロバイダーとブランチを API 経由で確認し、`--strict` では
警告も失敗として扱います。

### YAML からバッチ実行する

```shell
python -m analyze_git_repo_loc run --config ./config.yml
```

`run` は YAML に定義されたリポジトリと解析設定を読み込みます。
実行時の最小限の上書きとして、次のオプションを利用できます。

```shell
python -m analyze_git_repo_loc run --config ./config.yml --interval weekly --output ./reports --no-plot-show
```

## YAML 設定

YAML では、リポジトリと安定した解析設定を定義します。
`run` の CLI 上書きは `--output`, `--since`, `--until`, `--interval`,
`--no-plot-show` に限定されています。

```yaml
settings:
  output: output
  since: '2024-01-01'
  until: '2026-05-31'
  interval: monthly
  no_plot_show: false
  exclude_template_mode: auto

repositories:
  - path: https://github.com/example/project.git
    branch: main
    exclude_dirs:
      - node_modules
    exclude_template_mode: auto

interactive:
  providers:
    github:
      enabled: true
    gitlab:
      enabled: false
  defaults:
    clone_protocol: https
  quick_defaults:
    output: output
    interval: monthly
    cache_policy: use
    exclude_template_mode: auto
    lang:
      - Python
```

### 除外パステンプレート

`exclude_template_mode` は `auto`, `manual`, `off` を指定できます。
`auto` ではリポジトリ構成から Python / .NET / Unity / Node.js / Java /
Rust / Go の一般的な生成物・依存物ディレクトリを推定し、手動の
`exclude_dirs` と統合します。`manual` は `exclude_dirs` のみ、`off` は
除外なしで解析します。

独自テンプレートを使う場合は `settings.exclude_template_files` に YAML
ファイルを指定します。テンプレートには `name`, `display_name`, `detect`,
`exclude_dirs`, 任意の `priority` を定義できます。

`interactive.quick_defaults` は Quick Review で使う非シークレットの既定値です。
トークン、client ID、認証方式は保存しません。

`init` と `run -i` は、既存の `repositories` と、`repositories:` 配下の
`# - path: ...` のようなコメントアウト済みリポジトリ候補を保持しながら
設定を書き戻します。

`run -i` で保存したリポジトリには `include_subpath` が含まれることがあります。
解析時にはリポジトリルートからの相対サブパスとして扱われます。

`settings.workers` はリポジトリ解析の並列数です。複数エントリが同じローカル
Git root、または同じリモートキャッシュパスを指す場合は、`.git/config.lock`
競合を避けるため、その実行では 1 worker にフォールバックします。独立した
リポジトリ同士は設定された worker 数で並列解析します。

## 出力ファイル

出力ルートは YAML の `settings.output`、または `run --output` で指定します。
各実行ではタイムスタンプ付きディレクトリ (`YYYYMMDDHHMMSS`) を作成し、
実行単位の成果物を保存します。リポジトリ別の成果物は出力ルート直下に作成します。

主な実行ディレクトリの内容:

- `summary.md`: 実行サマリー。
- `repo_list.txt`: 実行対象のリポジトリとブランチ。
- `language_analysis.csv`, `author_analysis.csv`, `repository_trend_analysis.csv`
- `report.html` と `assets/`
- 複数リポジトリ時: `repository_chart.html`, `author_chart.html`,
  `author_contribution_contribution_chart.html`, および対応する
  `*_trend_data.csv` / `*_summary_data.csv`

リポジトリ別ディレクトリの主な内容:

- `loc_data.csv`
- `language_trends.csv`, `language_trend_data.csv`,
  `language_summary_data.csv`, `language_chart.html`
- `author_trends.csv`, `author_trend_data.csv`,
  `author_summary_data.csv`, `author_chart.html`

## ヘルプ

```shell
python -m analyze_git_repo_loc --help
python -m analyze_git_repo_loc init --help
python -m analyze_git_repo_loc doctor --help
python -m analyze_git_repo_loc run --help
```

## 対応言語

対応言語は次のコマンドで確認できます。

```shell
pygmentize -L lexers
```

## 作者

Nob Shinjo (<https://github.com/nobShinjo>)

## ライセンス

- [LICENSE](./LICENSE)
- [3rd Party Licenses](./3rdPartyLicenses.md)
