# AnalyzeGitRepoLOC

[日本語 README](./README.ja.md)

## Overview

Analyze Git repositories and visualize code LOC.

![Analysis Example](./docs/images/example.png)

## Release Notes

[CHANGELOG](./CHANGELOG.md)

## Requirement

1. Clone to git repository.

    ```shell
    git clone https://github.com/nobShinjo/AnalyzeGitRepoLoc
    ```

1. Create a virtual environment and install dependencies with `uv`.

    ```shell
    cd ./AnalyzeGitRepoLoc/
    uv venv --python 3.14
    # Windows PowerShell
    .venv\Scripts\Activate.ps1
    # macOS/Linux
    # source .venv/bin/activate
    uv sync --active
    ```

## Usage

### Command line

The CLI is organized around two subcommands:

```shell
python -m analyze_git_repo_loc init [--config config.yml]
python -m analyze_git_repo_loc run [--config config.yml] [options]
python -m analyze_git_repo_loc run -i [--config config.yml]
```

Use `init` to create a starter config, `doctor` to validate YAML before a run,
`run -i` for the guided interactive workflow, and `run` for non-interactive
batch analysis from YAML.

Direct `repo_paths` arguments are no longer a command-line entry point. Define
repositories in YAML, or select them with `run -i` and save the generated config.

### Remote authentication

The CLI prefers SSH keys for remote repositories. When SSH access is unavailable
it can fall back to HTTPS token authentication for GitHub or GitLab.

Set one of the following environment variables before running the CLI:

- `GITHUB_TOKEN`: GitHub personal access token for HTTPS authentication.
- `GITLAB_TOKEN`: GitLab personal access token for HTTPS authentication.

### Examples

#### Example : Create an initial config

```shell
python -m analyze_git_repo_loc init
```

`init` interactively creates a minimal interactive-ready YAML config. The default
output file is `config.yml`. If the file already exists, the CLI asks for
another file name; entering the same existing path requires explicit overwrite
confirmation.

The generated config stores common non-secret defaults only. It does not save
repositories, tokens, client IDs, or authentication choices. After creation,
run:

```shell
python -m analyze_git_repo_loc run -i
```

#### Example : Guided interactive analysis

```shell
python -m analyze_git_repo_loc run -i --config ./config.yml
```

The interactive run lists repositories from enabled GitHub/GitLab providers, lets you
search and select multiple repositories, then immediately runs the normal
analysis pipeline with the selected repositories.

When only one provider is configured and `GITHUB_TOKEN` / `GITLAB_TOKEN` or an
existing `gh` / `glab` login is available, `run -i` starts at Quick Review.
Press Enter to run, `e` to edit, `d` for details, `s` to save config then run,
or `c` to cancel.

#### Example : Validate configuration

```shell
python -m analyze_git_repo_loc doctor --config ./config.yml
```

`doctor` performs lightweight local checks for YAML structure, analysis settings,
repository paths, output paths, and secret-like keys. Add `--remote` to verify
configured GitHub/GitLab providers through their APIs, and `--strict` to treat
warnings as failures.

#### Example : Batch run from YAML

```shell
python -m analyze_git_repo_loc run --config ./config.yml
```

`run` reads repositories and stable analysis settings from YAML. A small set of
runtime overrides remains available:

```shell
python -m analyze_git_repo_loc run --config ./config.yml --interval weekly --output ./reports --no-plot-show
```

### YAML configuration

Use YAML to define repositories and stable analysis settings. `run` supports
only minimal CLI overrides: `--output`, `--since`, `--until`, `--interval`, and
`--no-plot-show`.

```yaml
settings:
  output: ./out
  interval: monthly
  since: 2023-01-01
  until: 2023-12-31
  lang:
    - Python
    - C#
    - Markdown
  author_name: "Alice,Bob"
  exclude_dirs:
    - docs
    - tests
  exclude_template_mode: auto
  exclude_template_names:
    - python
  workers: 4

repositories:
  - path: /path/to/repo1
    branch: main
    exclude_dirs:
      - tools
      - samples
    exclude_template_mode: auto
  - path: https://github.com/user/repo2.git
    branch: develop

interactive:
  providers:
    github:
      enabled: true
      api_base_url: https://api.github.com
    gitlab:
      enabled: false
      base_url: https://gitlab.com
  defaults:
    clone_protocol: https
  quick_defaults:
    interval: monthly
    cache_policy: use
    no_plot_show: true
    exclude_dirs:
      - node_modules
      - .venv
    exclude_template_mode: auto
```

Notes:

- `repositories` entries may be a string (path/URL) or a mapping with `path`,
  `branch`, `exclude_dirs`, `include_subpath`, and exclude template settings.
  Branch defaults to `main`.
- `lang`, `author_name`, `exclude_dirs`, `exclude_template_names`, and
  `exclude_template_files` accept a YAML list or a
  comma-separated string.
- `exclude_template_mode` can be `auto`, `manual`, or `off`. `auto` detects
  common project layouts and merges template excludes with manual
  `exclude_dirs`; `manual` uses only `exclude_dirs`; `off` disables excludes.
- Built-in exclude templates cover Python, .NET, Unity, Node.js, Java, Rust,
  and Go projects. Add `settings.exclude_template_files` to load custom
  template YAML files with `name`, `display_name`, `detect`, `exclude_dirs`,
  and optional `priority`.
- `init` can create a minimal starter config for interactive usage.
- `run -i` uses `config.yml` by default and may use a YAML file without
  `repositories`.
- `run -i` runs a pre-analysis review. YAML values are loaded as
  defaults, then the interactive flow confirms repository selection, branches, filters,
  path rules, output, cache policy, and display behavior before analysis starts.
- The interactive flow can ask which providers to use: GitHub, GitLab.com, and
  self-hosted GitLab. If exactly one provider is configured, that provider is
  selected automatically. The self-hosted GitLab URL can be entered at runtime.
- `interactive.quick_defaults` stores non-secret defaults used by the Quick Review
  screen. It never stores tokens, client IDs, or authentication choices.
- In the interactive flow, global excludes, per-repository excludes, and
  detected exclude templates are combined before analysis. Template-derived
  paths are kept even when they do not currently exist, and missing-path
  warnings are reserved for manual excludes.
- Quick Review starts with a compact summary and uses terminal colors when
  supported to distinguish headings, summary values, actions, and cache states.
  Press `d` to show repository-level details and full execution conditions.
- Interactive-selected repositories may include `include_subpath` when saving config;
  the analysis run treats it as a repository-root-relative subpath.
- Interactive authentication is selected at runtime. It offers environment tokens
  (`GITHUB_TOKEN` / `GITLAB_TOKEN`), existing `gh` / `glab` CLI login tokens,
  OAuth Device Code login when an application client ID is available, or a
  one-time token entered for the current run.
- Environment tokens and existing `gh` / `glab` logins are selected
  automatically when they are the configured provider's available non-interactive
  option. Device Code and one-time token authentication still require explicit
  selection.
- Interactive authentication details are not stored in YAML, files, or keyrings by this
  application. Resolved tokens are mirrored only into the current process
  environment for downstream clone compatibility.
- `interactive.defaults.clone_protocol` accepts `https` or `ssh`.

### Output files

The output root comes from `settings.output` in YAML, or from the `run --output`
override. Each run creates a timestamped directory (`YYYYMMDDHHMMSS`) with
run-level outputs, and per-repository folders are created directly under the
output root.

Run directory (timestamped) contents:

- `summary.md`: Markdown summary for the run.
- `repo_list.txt`: Repository and branch list used for the run.
- `language_analysis.csv`, `author_analysis.csv`, `repository_trend_analysis.csv`
- `report.html` and `assets/` (Tabler CSS/JS and Plotly JS).
- Multi-repo only: `repository_chart.html`, `author_chart.html`,
  `author_contribution_contribution_chart.html`, plus corresponding
  `*_trend_data.csv` and `*_summary_data.csv`.

Per-repository directory (under the output root) contents:

- `loc_data.csv`
- `language_trends.csv`, `language_trend_data.csv`,
  `language_summary_data.csv`, `language_chart.html`
- `author_trends.csv`, `author_trend_data.csv`,
  `author_summary_data.csv`, `author_chart.html`

The `.cache` directory under the output root stores remote clones and can be
cleared with the YAML `settings.clear_cache` value.

### Stdout examples

Example: stdout while running

```text
# Start analyze_git_repo_loc.
- Analyze Git repositories and visualize code LOC.

Analyzing repositories:  50%|=====     | 1/2 [00:06<00:06,  6.04s/it]

# Analysis of LOC in git repository: AnalyzeGitRepoLoc (main)
Analyzing commits:  42%|====      | 84/200 [00:03<00:04, 28.2commit/s]

# Forming dataframe type data.
Processing loc data:  50%|=====     | 1/2 [00:01<00:01,  1.10s/it]
```

Example: stdout when analysis completes 100%

```text
Analyzing repositories: 100%|==========| 2/2 [00:12<00:00,  6.02s/it]
# Save the analyzed data.
Saving analyzed data: 100%|==========| 3/3 [00:00<00:00, 52.3it/s]
# Generate charts.
Charts: Language trend: 100%|==========| 5/5 [00:02<00:00,  2.31it/s]
# Generate HTML report.
Generating HTML report: 100%|==========| 4/4 [00:01<00:00,  3.52it/s]

# LOC Analyze
                                                  FINISH
```

### Help

```shell
python -m analyze_git_repo_loc --help
```

```text
usage: analyze_git_repo_loc [-h] {init,run} ...

Analyze Git repositories and visualize code LOC.

positional arguments:
  {init,doctor,run}
    init          Create an initial YAML configuration file interactively.
    doctor        Validate YAML configuration before running analysis.
    run           Run analysis from a YAML configuration file, optionally interactively.

options:
  -h, --help      show this help message and exit
```

## Author

Nob Shinjo (<https://github.com/nobShinjo>)

## Licenses

- [LICENSE](./LICENSE)
- [3rd Party LicenSes](./3rdPartyLicenses.md)

## Languages

The available languages can be checked by executing the following command.

Please refer to [languages](./LANGUAGES.md) for the available programming languages.

[languages](./LANGUAGES.md)
