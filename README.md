# AnalyzeGitRepoLOC

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

1. Creation of virtual environments.

    ```shell
    cd ./AnalyzeGitRepoLoc/
    python -m venv .venv
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    ```

    または pip-toolsを使用する場合は、

    ```shell
    cd ./AnalyzeGitRepoLoc/
    python -m venv .venv
    python -m pip install --upgrade pip
    pip-sync --python-executable .venv/Scripts/python.exe
    ```

1. Install CLOC.

   - [Official Github project page](https://github.com/AlDanial/cloc)
   - [How to install cloc](https://github.com/AlDanial/cloc#install-via-package-manager)

## Usage

### Example : Monthly Analysis

  ```shell
  python -m analyze_git_repo_loc [repository_path] --interval monthly -o ./out 
  ```

### Example : Daily Analysis

  ```shell
  python -m analyze_git_repo_loc [repository_path] --interval daily -o ./out 
  ```

### Example : Specify branch name

  ```shell
  python -m analyze_git_repo_loc [repository_path] -b develop --interval daily -o ./out 
  ```

### Example : Filter by date

  ```shell
  python -m analyze_git_repo_loc [repository_path] --interval monthly -o ./out -s 2023-01-01 -e 2023-12-31
  ```

### Example : Filter by Language

  ```shell
  python -m analyze_git_repo_loc [repository_path] --interval monthly -o ./out --lang C#,Python,text,Markdown
  ```

### Example : Filter by Author

  ```shell
  python -m analyze_git_repo_loc [repository_path] --interval monthly -o ./out --author-name [author name] 
  ```

### Example : Multi repository

  ```shell
  python -m analyze_git_repo_loc [repository_path],[repository_path],[repository_path] --interval monthly -o ./out 
  ```

### Example : Clear old cache files

  ```shell
  python -m analyze_git_repo_loc [repository_path] --interval monthly -o ./out --clear_cache
  ```

### Help

  ```shell
  python -m analyze_git_repo_loc --help
  ```

  ```text
  usage: analyze_git_repo_loc [-h] [-o OUTPUT] [-s START_DATE] [-e END_DATE] [-b BRANCH] 
                            [--interval {daily,weekly,monthly}] [--lang LANG]
                            [--author-name AUTHOR_NAME] [--clear_cache]
                            repo_paths

  Analyze Git repositories and visualize code LOC.

  positional arguments:
    repo_paths            Comma-separated list of Git repository paths

  options:
    -h, --help            show this help message and exit
    -o OUTPUT, --output OUTPUT
                          Output path
    -s START_DATE, --start_date START_DATE
                          Start Date yyyy-mm-dd
    -e END_DATE, --end_date END_DATE
                          End Date yyyy-mm-dd
    -b BRANCH, --branch BRANCH
                          Branch name (default: main)
    --interval {daily,weekly,monthly}
                          Interval (default: monthly)
    --lang LANG           Count only the given space separated, case-insensitive languages L1,L2,L3, etc. Use 'cloc
                          --show-lang' to see the list of recognized languages.
    --author-name AUTHOR_NAME
                        Author name to filter commits
    --clear_cache         If set, the cache will be cleared before executing the main function.
  ```

## Author

Nob Shinjo (<https://github.com/nobShinjo>)

## Licenses

- [LICENSE](./LICENSE)
- [3rd Party LicenSes](./3rdPartyLicenses.md)

## Languages

The available languages can be checked by executing the following command.

```shell
cloc --show-lang
```

[languages](./LANGUAGES.md)
