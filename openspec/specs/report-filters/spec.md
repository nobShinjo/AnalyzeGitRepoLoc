# report-filters Specification

## Purpose
TBD - created by archiving change add-report-filters. Update Purpose after archive.
## Requirements
### Requirement: Tag-based table filters

The HTML report SHALL provide tag-based filters for language, author, and repository tables within each tab.

#### Scenario: Filter language table with tags

- **WHEN** a user disables a language tag in a tab
- **THEN** the language table updates to exclude that language

### Requirement: Table-only filtering

The HTML report SHALL apply filter selections to tables only, leaving charts unchanged.

#### Scenario: Apply filters with charts present

- **WHEN** a user toggles tags in a tab
- **THEN** the tables update and charts remain unchanged

### Requirement: Tag defaults and click behavior

The HTML report SHALL show all tags enabled by default, disable tags via the "x" control, re-enable disabled tags on click, and apply "only" selection when all tags are enabled.

#### Scenario: Disable a tag

- **WHEN** a user clicks the "x" on an enabled tag
- **THEN** the tag becomes disabled

#### Scenario: Select only one tag while all are enabled

- **WHEN** all tags in a group are enabled and a user clicks a tag
- **THEN** only that tag remains enabled

#### Scenario: Ignore active tag clicks when some tags are disabled

- **WHEN** a user clicks an enabled tag while some tags are disabled
- **THEN** the enabled tag state remains unchanged

#### Scenario: Re-enable a disabled tag

- **WHEN** a user clicks a disabled tag
- **THEN** the tag becomes enabled

### Requirement: Tag search and clear filters

The HTML report SHALL include a search box above each tag group and a clear filters action that enables all tags.

#### Scenario: Clear tag filters

- **WHEN** a user selects clear filters in a tag group
- **THEN** all tags in that group become enabled

### Requirement: Tag ordering by NLOC

The HTML report SHALL sort tag lists by total NLOC in descending order.

#### Scenario: Render a tag list

- **WHEN** tags are rendered
- **THEN** they are ordered by NLOC descending

### Requirement: Language table sum row

The HTML report SHALL include a Sum row at the end of each language table to reflect totals and visually distinguish the summary row.

#### Scenario: Display language summary

- **WHEN** a language table is rendered
- **THEN** the final row shows summed totals and is visually emphasized

### Requirement: Fixed report controls

The HTML report SHALL keep the title and tab navigation visible while report cards scroll.

#### Scenario: Scroll report content

- **WHEN** a user scrolls tables or charts
- **THEN** the title and tabs remain visible

### Requirement: Local tab filters

The HTML report SHALL apply filter selections only within the current tab.

#### Scenario: Filter within a tab

- **WHEN** a user applies filters in a tab
- **THEN** other tabs remain unaffected by those selections

