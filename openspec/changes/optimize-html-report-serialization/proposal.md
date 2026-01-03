# Change: Optimize HTML report filter serialization

## Why
HTML report generation is a hotspot for large datasets, especially while building
filter payload rows. Vectorized serialization can reduce runtime while preserving
output behavior.

## What Changes
- Build filter row payloads using vectorized DataFrame transformation.
- Preserve progress reporting semantics for filter row generation.

## Impact
- Affected specs: html-report
- Affected code: analyze_git_repo_loc/html_report.py
