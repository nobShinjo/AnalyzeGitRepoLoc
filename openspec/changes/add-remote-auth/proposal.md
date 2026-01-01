# Change: Add remote repository authentication

## Why
Some remote repositories require authentication, so the tool should support SSH keys and access tokens.

## What Changes
- Prefer SSH key authentication for remote clones.
- Support GitHub/GitLab tokens via environment variables when HTTPS auth is required.

## Impact
- Affected specs: remote-auth
- Affected code: clone/auth handling, environment variable configuration

## Dependencies
- Depends on change: add-remote-repos
