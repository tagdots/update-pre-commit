# CHANGELOG

## 1.2.11 (2026-08-14)

## 1.2.10 (2026-08-14)

### Fix

- upgrade packages in pyproject.toml to address vulnerabilities
- update pre-commit-config and pyproject.toml accordingly

## 1.2.5 (2025-11-13)

### Fix

- add a prefix to new branch name to label PR
- update github-url

## 1.2.3 (2025-11-08)

### Fix

- upgrade to use Python 3.14
- update deps and add uv to make
- update cron-tasks - delete-workflow-runs and delete-branches
- add "fail-on-severity: low" to the configuration to low level vuln alert
- resolve stuck version comment
- replace stale-branches with delete-branches-action
- resolve minor typos in actions

### Refactor

- improve code quality - type hint, static checking, streamline functions

## 1.1.31 (2025-08-15)

### Fix

- replace the cron task that deletes workflow runs

## 1.1.23 (2025-07-26)

### Feat

- add badges to cron-tasks

### Fix

- resolve checkout using git rather than https

## 1.1.20 (2025-07-22)

### Feat

- add UPC to cron tasks

### Fix

- coverage run issues: use command_line, simplify Makefile, & use outdated config
- fix typos and clarify documentation

## 1.1.9 (2025-06-10)

### Fix

- sleep delays validation to ensure publish is complete

## 1.1.0 (2025-05-23)

### Feat

- add --open-pr option feature

### Fix

- update package name

## 1.0.0 (2025-05-22)

### Feat

- add badges on README
- add CD-production workflow
- add CD-staging workflow
- add cron-coverage to perform coverage
- initial release setup

### Fix

- env var not passed to sed properly
