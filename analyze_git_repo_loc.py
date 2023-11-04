"""
Analyze Git repositories and visualize code LOC.

"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px


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
                "./cloc.exe",
                "--by-file-by-lang",
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
    pivot_data = grouped_data.pivot(index="month", columns="language", values="code")
    fig = px.area(
        data_frame=pivot_data,
        x="month",
        y="loc",
        title="LOC by Language per Month",
        color="language",
    )
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
        if cloc_output:
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
    args = parser.parse_args()

    # 出力先ディレクトリ作成
    output_dir: str = os.path.join(
        os.getcwd().replace(os.sep, "/"), args.output
    ).replace(os.sep, "/")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # gitリポジトリ解析
    loc_data: pd.DataFrame = analyze_git_repo_loc(
        repo_path=args.repo_path,
        start_date_str=args.start_date,
        end_date_str=args.end_date,
        output_path=output_dir,
    )
    # Chart出力
    plot_data(monthly_data=loc_data, output_path=output_dir)
