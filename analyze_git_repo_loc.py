"""
Analyze Git repositories and visualize code LOC.

"""

import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px


def run_cloc(
    repo_path: str, start_date: datetime, end_date: datetime, output_path: str
):
    """
    run_cloc 指定したgitリポジトリに対して、cloc解析する

    Args:
        repo_path (str): Git リポジトリパス
        start_date (datetime): 開始日付
        end_date (datetime): 終了日付
        output_path (str): ファイル出力先

    Returns:
        str: cloc解析結果(json形式)
    """

    output_filename: str = os.path.join(
        output_path, f"cloc_output_{end_date.strftime('%Y%m')}.json"
    )
    result = subprocess.run(
        [
            "cloc",
            "--by-file",
            "--json",
            "--git",
            f'--include-d={start_date.strftime("%Y-%m-%d")},{end_date.strftime("%Y-%m-%d")}',
            f"--out={output_filename}",
            repo_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout


def process_cloc_output(cloc_output: pd.DataFrame) -> pd.DataFrame:
    """
    process_cloc_output clocコマンドのjson出力をpd.DataFrameに変換する

    Args:
        cloc_output (DataFrame): clocコマンドのjson形式の出力文字列

    Returns:
        pd.DataFrame: (各言語名, LOCカウント数)のDataFrame
    """
    data_dict = json.loads(cloc_output)
    language_data = data_dict["SUM"]
    language_data.pop("header", None)
    language_data.pop("nFiles", None)
    data: pd.DataFrame = pd.DataFrame.from_dict(
        language_data, orient="index", columns=["code"]
    )
    data["language"] = data.index
    return data


def plot_data(monthly_data: pd.DataFrame, output_path: str):
    """
    plot_data グラフを表示, 保存する

    Args:
        monthly_data (DataFrame): 各月のLOC数データ
        output_path (str): ファイル出力先
    """
    fig = px.bar(
        monthly_data, x="language", y="code", title="LOC by Language per Month"
    )
    fig.show()
    fig.write_html(os.path.join(output_path, "report.html"))


def analyze_git_repo_loc(
    repo_path: str, start_date: datetime, end_date: datetime, output_path: str
) -> pd.DataFrame:
    """
    analyze_git_repo_loc Gitリポジトリ内のLOC（Lines Of Code）を分析し、指定された日付範囲内の変更量を計算します。

    Parameters:
        repo_path (str): Gitリポジトリへのパス
        start_date (datetime): 開始日付
        end_date (datetime): 終了日付
        output_path (str): ファイル出力先

    Returns:
        loc_dict (DataFrame): 各月のLOC数データ
    """
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    current_date: datetime = start_date
    all_data: pd.DataFrame = None

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
        monthly_data: pd.DataFrame = process_cloc_output(cloc_output)
        monthly_data["month"] = current_date.strftime("%Y-%m")
        if all_data is None:
            all_data = monthly_data
        else:
            all_data = pd.concat([all_data, monthly_data])
        current_date = next_date
    return all_data


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
if not os.path.exists(args.output):
    os.mkdir(args.output)

# gitリポジトリ解析
loc_data: pd.DataFrame = analyze_git_repo_loc(
    repo_path=args.repo_path,
    start_date=args.start_date,
    end_date=args.end_date,
    output_path=args.output,
)
# Chart出力
plot_data(monthly_data=loc_data, output_path=args.output)
