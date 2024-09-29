# Changelog

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

- b909682 Refactor code to handle empty dataframes in language and author trend charts
- 84b2097 Fix incorrect code aggregation in loc_trend_by_author by specifying aggfunc='sum'
- 8880298 refactor:  cloc_exe_filename to handle different operating systems

## [1.0.0] - 2023-12-18

### Added

- Initial release.
- Provided basic functionality to analyze LOC in a Git repository.
- Provided functionality to generate LOC trend charts by language and author.

[1.1.0](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v1.1.0)
[1.0.0](https://github.com/nobShinjo/AnalyzeGitRepoLoc/releases/tag/v1.0.0)
