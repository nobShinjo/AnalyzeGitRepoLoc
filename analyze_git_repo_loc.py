"""
Analyze Git repositories and visualize code LOC.

"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from os.path import abspath

import pandas as pd
import plotly.express as px
from git import Commit, Repo
from plotly.subplots import make_subplots

# Global variables
CURRENT_PATH: str = os.getcwd()
""" カレントパス """


def get_commits(
    repo_path: str,
    branch: str,
    start_date: datetime,
    end_date: datetime,
    interval="daily",
) -> list[Commit]:
    """
    get_commits Get a list of Commit object.

    This function retrieves a list of commits for a given repository and branch.
    It filters for a given date/time range and a given interval.

    Args:
        repo_path (str): The file system path to the Git repository.
        branch (str): The name of the branch to retrieve commits from.
        start_date (datetime): The start date for filtering commits.
        end_date (datetime): The end date for filtering commits.
        interval (str, optional): The interval to use for filtering commits. Defaults to 'daily'.

    Raises:
        ValueError: If the provided `interval` is not one of 'daily', 'weekly', or 'monthly'.

    Returns:
        list[Commit]: A list of commit object.
    """

    # Initialize the repository object
    repo = Repo(repo_path)

    # Set the timedelta object that defines the interval.
    # NOTE: Approximate average length of month in days
    intervals = {
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(days=30),
    }
    delta = intervals.get(interval)
    if not delta:
        raise ValueError("Invalid interval. Choose 'daily', 'weekly', or 'monthly'.")

    # Start and end dates to filter
    since = f'--since="{start_date.strftime("%Y-%m-%d")}"'
    until = f'--until="{end_date.strftime("%Y-%m-%d")}"'

    # Search and filter commits in order and add them to the list
    # NOTE: Commit dates are ordered by newest to oldest, so filter by end date
    last_added_commit_date = end_date
    commits: list[Commit] = []
    for commit in repo.iter_commits(branch, since=since, until=until):
        commit_date = datetime.fromtimestamp(commit.committed_date)
        if commit_date <= last_added_commit_date - delta:
            # commits.append((commit.hexsha, commit_date.strftime("%Y-%m-%d %H:%M:%S")))
            commits.append(commit)
            last_added_commit_date = commit_date

    return commits


def store_commits_to_database(db_path: str, commits):
    # SQLite3 DBへ接続する
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # テーブルが存在しない場合は作成する
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS commits (
            hash TEXT PRIMARY KEY,
            date TEXT NOT NULL
        )
    """
    )

    # コミット情報をデータベースに格納する
    cursor.executemany(
        """
        INSERT OR IGNORE INTO commits (hash, date)
        VALUES (?, ?)
    """,
        commits,
    )

    # 変更をコミットし、閉じる
    conn.commit()
    conn.close()


# 使用例:
db_path = "path/to/your/database.db"


def run_cloc(
    repo_path: str, start_date: datetime, end_date: datetime, output_path: str
) -> str:
    """
    run_cloc 指定したgitリポジトリに対して、cloc解析する

    Args:
        repo_path (str): Git リポジトリパス
        start_date (datetime): 開始日付
        end_date (datetime): 終了日付
        output_path (str): ファイル出力先

    Returns:
        str: cloc解析結果(json形式)

    Remarks:
        git log コマンドで開始日付から終了日付までの変更を検索し、clocコマンドで詳細のLOCを解析する
        cloc --by-file --json --git
    """

    try:
        os.chdir(repo_path)
        git_log = subprocess.run(
            [
                "git",
                "log",
                f"--since={start_date.strftime('%Y-%m-%d')}",
                f"--until={end_date.strftime('%Y-%m-%d')}",
                "--name-only",
                "--pretty=format:",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        if not git_log.stdout:
            return ""

        # git_log.stdoutから、空行は削除して、カンマ区切りのファイル名を連結いた文字列を作成する
        files = ",".join([file for file in git_log.stdout.split("\n") if file.strip()])

    except subprocess.CalledProcessError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(-1)

    if files is None:
        return ""

    try:
        # output_filename: str = os.path.join(
        #     output_path, f"cloc_output_{start_date.strftime('%Y%m')}.json"
        # )

        result = subprocess.run(
            [
                f"{CURRENT_PATH}/cloc.exe",
                "--json",
                "--vcs=git",
                f"--list-file={files}",
                repo_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(-1)

    return result.stdout


def process_cloc_output(cloc_output: pd.DataFrame, month: datetime) -> pd.DataFrame:
    """
    process_cloc_output clocコマンドのjson出力をpd.DataFrameに変換する

    Args:
        cloc_output (DataFrame): clocコマンドのjson形式の出力文字列
        month (datetime): データ対称年月

    Returns:
        pd.DataFrame: (各言語名, LOCカウント数)のDataFrame
    """

    data_dict = json.loads(cloc_output)
    language_data = data_dict["by_lang"]
    language_data.pop("header", None)
    language_data.pop("nFiles", None)
    data = pd.DataFrame.from_dict(language_data, orient="index", columns=["code"])
    data["month"] = month
    data["language"] = data.index
    return data


def plot_data(monthly_data: pd.DataFrame, output_path: str):
    """
    plot_data グラフを表示, 保存する

    Args:
        monthly_data (DataFrame): 各月のLOC数データ
        output_path (str): ファイル出力先
    """

    grouped_data = monthly_data.groupby(["month", "language"]).sum().reset_index()
    language_data = grouped_data.pivot(index="month", columns="language", values="code")
    sum_data = language_data.pop("SUM")

    # 言語別統計
    fig_lang = px.area(data_frame=language_data, color="language")
    fig_lang_traces = []
    for trace in range(len(fig_lang["data"])):
        fig_lang_traces.append(fig_lang["data"][trace])

    # 合計LOC
    fig_sum = px.line(data_frame=sum_data)
    fig_sum_traces = []
    for trace in range(len(fig_sum["data"])):
        fig_sum["data"][trace]["showlegend"] = False
        fig_sum_traces.append(fig_sum["data"][trace])

    fig = make_subplots(
        rows=1,
        cols=1,
        x_title="Month",
        y_title="LOC",
    )
    fig.update_layout(
        title={"text": "LOC by Language / Month", "x": 0.5, "xanchor": "center"}
    )

    for traces in fig_lang_traces:
        fig.append_trace(traces, row=1, col=1)
    for traces in fig_sum_traces:
        fig.append_trace(traces, row=1, col=1)
    fig.show()
    fig.write_html(os.path.join(output_path, "report.html"))


def analyze_git_repo_loc(
    repo_path: str, start_date_str: str, end_date_str: str, output_path: str
) -> pd.DataFrame:
    """
    analyze_git_repo_loc Gitリポジトリ内のLOC（Lines Of Code）を分析し、指定された日付範囲内の変更量を計算します。

    Parameters:
        repo_path (str): Gitリポジトリへのパス
        start_date (str): 開始日付
        end_date (str): 終了日付
        output_path (str): ファイル出力先

    Returns:
        loc_dict (DataFrame): 各月のLOC数データ
    """

    # 開始、終了日付を定義
    try:
        start_date: datetime = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date: datetime = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(-1)

    current_date: datetime = start_date
    all_data: pd.DataFrame = pd.DataFrame()

    while current_date <= end_date:
        next_date: datetime = (
            current_date.replace(day=1) + timedelta(days=32)
        ).replace(day=1)
        cloc_output: str = run_cloc(
            repo_path=repo_path,
            start_date=current_date,
            end_date=next_date,
            output_path=output_path,
        )
        monthly_data: pd.DataFrame = pd.DataFrame()
        if cloc_output and cloc_output != "{}\n":
            monthly_data = process_cloc_output(
                cloc_output=cloc_output, month=current_date.strftime("%Y-%m")
            )
        all_data = pd.concat([all_data, monthly_data])
        current_date = next_date
    return all_data


if __name__ == "__main__":
    # コマンドライン引数解析
    parser = argparse.ArgumentParser(
        prog="Analyze Git Repository LOC",
        description="Analyze Git repositories and visualize code LOC.",
    )
    # pylint: enable=line-too-long
    parser.add_argument("repo_path", type=str, help="Path of Git repository")
    parser.add_argument("-o", "--output", type=str, default="./out", help="Output path")
    parser.add_argument("-s", "--start_date", type=str, help="Start Date yyyy-mm-dd")
    parser.add_argument("-e", "--end_date", type=str, help="End Date yyyy-mm-dd")
    parser.add_argument(
        "-b", "--branch", type=str, default="main", help="Branch name (default: main)"
    )
    parser.add_argument(
        "--interval",
        choices=["daily", "weekly", "monthly"],
        default="monthly",
        help="Interval (default: monthly)",
    )
    args = parser.parse_args()

    # 出力先ディレクトリ作成
    output_dir: str = os.path.join(
        os.getcwd().replace(os.sep, "/"), args.output
    ).replace(os.sep, "/")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # 出力ディレクトリに解析結果を格納するSQLite Datebaseファイルを作成する
    db_path: str = os.path.join(output_dir, "analysis_results.db")

    # gitリポジトリ解析
    loc_data: pd.DataFrame = analyze_git_repo_loc(
        repo_path=abspath(args.repo_path),
        start_date_str=args.start_date,
        end_date_str=args.end_date,
        output_path=output_dir,
    )
    # Chart出力
    plot_data(monthly_data=loc_data, output_path=output_dir)
