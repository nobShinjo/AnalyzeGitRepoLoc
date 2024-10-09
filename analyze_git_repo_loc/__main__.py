"""
Analyze Git repositories and visualize code LOC.

Author:    Nob Shinjo
"""

import argparse
import os
import sys
from datetime import datetime

import pandas as pd
from colorama import Cursor, Fore, Style

from .colored_console_printer import ColoredConsolePrinter
from .git_repo_loc_analyzer import GitRepoLOCAnalyzer
from .utils import analyze_and_save_loc_data, parse_arguments


def main():
    """
    main function to execute the program.
    """
    # Parsing command line arguments
    parser = argparse.ArgumentParser(
        prog="analyze_git_repo_loc",
        description="Analyze Git repositories and visualize code LOC.",
    )
    args = parse_arguments(parser)

    # Initialize ColoredConsolePrinter
    console = ColoredConsolePrinter()

    # Output program name and description.
    console.print_h1(f"# Start {parser.prog}.")
    print(Style.DIM + f"- {parser.description}", end=os.linesep + os.linesep)

    all_loc_data = []

    for repo_path in args.repo_paths:
        # Create GitRepoLOCAnalyzer
        try:
            analyzer = GitRepoLOCAnalyzer(
                repo_path=repo_path,
                branch_name=args.branch,
                cache_dir=args.output / ".cache",
                output_dir=args.output,
            )
        except FileNotFoundError as ex:
            print(f"Error: {str(ex)}", file=sys.stderr)
            sys.exit(1)

        # Remove cache files
        if args.clear_cache:
            try:
                console.print_h1("# Remove cache files.")
                analyzer.clear_cache_files()
                console.print_ok(up=2, forward=50)
            except FileNotFoundError as ex:
                print(f"Error: {str(ex)}", file=sys.stderr)
                sys.exit(1)

        # Analyze LOC against the git repository.
        console.print_h1(f"# Analyze LOC against the git repository: {repo_path}")
        loc_data = analyzer.analyze_git_repo_loc(
            branch=args.branch,
            since_str=args.since,
            until_str=args.until,
            interval=args.interval,
            lang=args.lang,
            author=args.author_name,
        )
        all_loc_data.append(loc_data)

        # Create output directory for the repository
        repo_output_dir = args.output / repo_path.name
        repo_output_dir.mkdir(parents=True, exist_ok=True)

        # Forming dataframe type data.
        console.print_h1("# Forming dataframe type data.")

        # Combine processing into one consistent step to reduce duplication.
        analyze_and_save_loc_data(
            loc_data=loc_data,
            output_path=repo_output_dir,
            analyzer=analyzer,
            interval=args.interval,
        )

    if len(args.repo_paths) > 1:
        # Combine all LOC data
        combined_loc_data = pd.concat(all_loc_data)

        # Create output directory for the combined data
        combined_output_dir = args.output / datetime.now().strftime("%Y%m%d%H%M%S")
        combined_output_dir.mkdir(parents=True, exist_ok=True)

        # Forming dataframe type data.
        console.print_h1("# Forming dataframe type data.")
        analyze_and_save_loc_data(
            loc_data=combined_loc_data,
            output_path=combined_output_dir,
            analyzer=analyzer,
            interval=args.interval,
        )

        # Save the list of repositories
        with open(combined_output_dir / "repo_list.txt", "w", encoding="utf-8") as f:
            f.write("\n".join([str(repo) for repo in args.repo_paths]))

    console.print_h1("# LOC Analyze")
    print(Cursor.UP() + Cursor.FORWARD(50) + Fore.GREEN + "FINISH")


if __name__ == "__main__":
    main()
