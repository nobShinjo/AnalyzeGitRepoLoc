# Changelog

## [1.3.0] - 2024-10-10

### Added

- d93d32a feat(analyzer): add branch name to chart titles and analysis
- 4dd19e2 feat(analyze_git_repo_loc): add script for analyzing git repository lines of code

### Changed

- update pip packages
  - e5e7263 update: third-party library versions in 3rdPartyLicenses.md
  - d8b3854 Update dev-requirements.txt and requirements.txt
- 1862d53 feat(analyze_git_repo_loc): add modular architecture and initial implementation

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

[1.1.1](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v1.1.1)
[1.1.0](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v1.1.0)
[1.0.0](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v1.0.0)
