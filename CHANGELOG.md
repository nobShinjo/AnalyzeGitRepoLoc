# Changelog

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

### Security

## [2.2.1] - 2024-12-24

### Fixed

- 33eacc7 Ensure paths and parameters are correctly quoted in `analyze_git_repo_loc.ps1` to handle spaces and special characters.
- 8e0875e Convert date arguments to datetime objects. Converted 'since' and 'until' arguments from strings to datetime objects in the main function.
-

## [2.2.0] - 2024-12-18

### Added

- Introduced a new feature to exclude specified directories from analysis using the `--exclude-dirs` option. Multiple directories can be separated by commas and should be specified as relative paths from the repository root.
- Added new parameters to `Scripts\analyze_git_repo_loc.ps1` to specify the output directory, date range, analysis interval, languages, author name, and cache clearing.
- Added help descriptions for these parameters in  `Scripts\analyze_git_repo_loc.ps1`.

## [2.1.3] - 2024-10-18

### Added

- Added stack trend chart for code volume by author in `analyze_git_repo_loc`.

### Changed

- Refactored `launch.json` to add `--no-plot-show` option.
- Improved data preparation and chart generation in `data-processing` by optimizing cumulative sum calculations, simplifying groupby and pivot operations, and enhancing readability.
- Refactored chart title handling in `generate_trend_chart` and `ChartBuilder` by renaming `sub_title` parameter to `title` for clarity and consistency.

## [2.1.2] - 2024-10-16

### Changed

- Renamed the `repository_analysis` variable to `repository_trend_analysis` for improved clarity, reflecting its specific use for trend analysis.
- Reorganized how analyzed data is saved by consolidating DataFrame parameters into a dictionary, which simplifies the `save_analysis_data` function.
- Updated chart generation functions and their arguments to ensure consistency across repository and author-related analyses.
- Modified chart titles to emphasize NLOC (non-blank lines of code) trends.

## [2.1.1] - 2024-10-15

### HotFixed

- Fixed an issue where using the `--clear-cache` option did not properly clear cached data, causing analysis to use outdated data. Initialized `_cache_commit_data` attribute to `None` in `GitRepoLOCAnalyzer` class to ensure proper cache handling.

## [2.1.0] - 2024-10-15

### Added

- Added `--no-plot-show` option for non-interactive environments in CLI.
- Added author contribution chart generation in `charts`.

### Changed

- Updated `launch.json` to include C++ language in the list of supported languages.
- Updated third-party dependencies in `3rdPartyLicenses.md`.
- Updated analyze_git_repo_loc settings in scripts.
- Updated `.vscode/settings.json` with new autocomplete options.

### Fixed

- Refactored `language_extensions.py` to remove duplicate file extensions and commented out code.
- Refactored `git_repo_loc_analyzer.ps1` to update repository list file path.
- Refactored `git_repo_loc_analyzer.py` to remove unused imports and update dependencies.
- Refactored `generate_repository_trend_chart` function to skip generating chart if data is empty or there is only one repository.

## [2.0.0] - 2024-10-14

### Added

- Introduced new modular architecture.
- Added `__init__.py` to `analyze_git_repo_loc` package to define module exports.

### Changed

- Switched from __GitPython__ to __Pydriller__ for commit processing.
- Updated `create_trend_trace` method in `ChartBuilder` class to improve trace addition.
- Updated third-party library versions in `3rdPartyLicenses.md`.
- Enhanced threading support and code clarity in `git_repo_loc_analyzer`.
- Improved console output and chart generation progress handling in `main`.
- Consolidated summary data aggregation logic in `main`.
- Enhanced repository trend analysis with Plotly in `charts`.
- Improved language filtering and LOC calculation in `analyze_git_repo_loc`.

### Fixed

- Fixed legend font size setting in `update_fig` method of `ChartBuilder` class.
- Corrected title text format in LOC trend chart in `chart_builder`.

## [1.3.0] - 2024-10-10

### Added

- d93d32a feat(analyzer): add branch name to chart titles and analysis
- 4dd19e2 feat(analyze_git_repo_loc): add script for analyzing git repository lines of code

### Changed

- update pip packages
  - e5e7263 update: third-party library versions in 3rdPartyLicenses.md
  - d8b3854 Update dev-requirements.txt and requirements.txt
- 1862d53 feat(analyze_git_repo_loc): add modular architecture and initial implementation
- 32c1f94 feat(scripts): externalize repository list to file in analyze script
- eba218c refactor(.vscode): add missing dependency 'ffill' to settings.json
- f24dcf6 refactor(loc_analysis): enhance LOC data combination logic
- f9104e3 refactor(utils): rename function for clarity and add sorting

## [1.2.0] - 2024-10-07

### Added

- b7bbde7 feat(git-repo-loc): enhance multi-repo support and error handling

## [1.1.1] - 2024-10-07

### Changed

- 961e8e4 refactor: chart builder to support custom x-axis tick format

### Fixed

- 5939673 feat(analyzer): add author-based filtering and trend analysis

## [1.1.0] - 2024-09-30

### Added

- Add CHANGELOG.md
- Support filtering commits by author.
- Add author trend chart.
- Combine language and author trend charts
- f2f041a add: dev-requirements.txt and dev-requirements.in (pip-tools)

### Changed

- 622de5b refactor: return type annotation in build method of ChartBuilder
- 4b8329e update: requirements.txt and requirements.in (pip-tools)
- update: README.md

### Fixed

- b909682 Refactor code to handle empty dataframe in language and author trend charts
- 84b2097 Fix incorrect code aggregation in loc_trend_by_author by specifying aggfunc='sum'
- 8880298 refactor:  cloc_exe_filename to handle different operating systems

## [1.0.0] - 2023-12-18

### Added

- Initial release.
- Provided basic functionality to analyze LOC in a Git repository.
- Provided functionality to generate LOC trend charts by language and author.
-

[2.2.1](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v2.2.1)
[2.2.0](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v2.2.0)
[2.1.3](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v2.1.3)
[2.1.2](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v2.1.2)
[2.1.1](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v2.1.1)
[2.1.0](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v2.1.0)
[2.0.0](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v2.0.0)
[1.1.1](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v1.1.1)
[1.1.0](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v1.1.0)
[1.0.0](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v1.0.0)
