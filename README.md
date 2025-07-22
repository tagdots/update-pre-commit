# Update-Pre-Commit

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/10601/badge)](https://www.bestpractices.dev/projects/10601)
[![CI](https://github.com/tagdots/update-pre-commit/actions/workflows/ci.yaml/badge.svg)](https://github.com/tagdots/update-pre-commit/actions/workflows/ci.yaml)
[![Code Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/tagdots/update-pre-commit/refs/heads/badge/coverage.json)](https://github.com/tagdots/update-pre-commit/actions/workflows/cron-coverage.yaml)

## 😎 Why you need update-pre-commit?
If you are already using `pre-commit` or you are planning to use `pre-commit` to enforce coding standard and detect issues before code check-in, **update-pre-commit** updates hooks revs in `.pre-commit-config.yaml` and automate creating pull request.

<br>

## ⭐ Why switch to update-pre-commit?
- we outperform others in update speed by more than `70%` (with minimum 4 hooks).
- we reduce your supply chain risks with `openssf best practices` in our development and operation.
- we automate your `change management` operations with built-in feature to create pull request on **GitHub**.
- we protect you against unreliable revs with tag such as `alpha`, `beta`, `prerelease`, and `rc`.

<br>

### Use Case 1️⃣ - running on GitHub action
Please visit our GitHub action ([update-pre-commit-action](https://github.com/marketplace/actions/update-pre-commit-action)) on the `GitHub Marketplace`.

<br>

### Use Case 2️⃣ - running locally on your computer
**Prerequisites**
```
* Python (3.12+)
  □ install pre-commit.

* GitHub
  □ create a fine-grained token with repository permissions (see below).
```

![GitHub Token Permission](https://raw.githubusercontent.com/tagdots/update-pre-commit/refs/heads/main/assets/github_token-permissions.png)

<br>

## 🔆 Install update-pre-commit

In the command-line examples below, we use a GitHub project named `hello-world`.  This project has `pre-commit` installed and a valid `.pre-commit-config.yaml`.

We will first install **update-pre-commit** in a virtual environment named after the project.  Next, we will run **update-pre-commit** with different options and show the results.

```
~/work/hello-world $ workon hello-world
(hello-world) ~/work/hello-world $ export GH_TOKEN=github_pat_xxxxxxxxxxxxx
(hello-world) ~/work/hello-world $ pip install -U update-pre-commit
```

<br>

## 🔍 Using update-pre-commit

🏃 _**Run to show command line usage and options**_: `--help`

```
(hello-world) ~/work/hello-world $ update-pre-commit --help

Usage: update-pre-commit [OPTIONS]

Options:
  --file TEXT        default: .pre-commit-config.yaml
  --dry-run BOOLEAN  default: true
  --open-pr BOOLEAN  default: false
  --version          Show the version and exit.
  --help             Show this message and exit.
```

<br><br>

🏃 _**Run to show version**_: `--version`

```
(hello-world) ~/work/hello-world $ update-pre-commit --version
update-pre-commit, version 1.0.0
```

<br><br>

🏃 _**Run default (without any options)**_

By default, **update-pre-commit** implicitly runs `--dry-run true --open-pr false`.

Thus, **update-pre-commit**:
1. reads `.pre-commit-config.yaml`.
1. produces a list of out-of-date pre-commit hooks on screen.<br>
(**NO** changes will be made to `.pre-commit-config.yaml`)

```
(hello-world) ~/work/hello-world $ update-pre-commit

Starting update-pre-commit on .pre-commit-config.yaml (dry-run True open-pr False)...

hadolint/hadolint (v2.11.0) is not using the latest release rev (v2.12.0)
pycqa/flake8 (7.1.2) is not using the latest release tag (7.2.0)
antonbabenko/pre-commit-terraform (v1.98.0) is not using the latest release rev (v1.98.1)

Update revs in .pre-commit-config.yaml: None
```

<br><br>

🏃 _**Run to update out-of-date hooks**_: `--dry-run false`

**update-pre-commit**:
1. reads `.pre-commit-config.yaml`.
1. produce a list of out-of-date pre-commit hooks on screen.
1. update `.pre-commit-config.yaml`.

```
(hello-world) ~/work/hello-world $ update-pre-commit --dry-run false

Starting update-pre-commit on .pre-commit-config.yaml (dry-run False open-pr False)...

hadolint/hadolint (v2.11.0) is not using the latest release rev (v2.12.0)
pycqa/flake8 (7.1.2) is not using the latest release tag (7.2.0)
antonbabenko/pre-commit-terraform (v1.98.0) is not using the latest release rev (v1.98.1)

Update revs in .pre-commit-config.yaml: Success
```

<br><br>

🏃 _**Run to update out-of-date hooks and open a pull request**_: `--dry-run false --open-pr true`

**update-pre-commit**:
1. reads `.pre-commit-config.yaml`.
1. produces a list of out-of-date pre-commit hooks on screen.
1. update `.pre-commit-config.yaml`.
1. checkout a new git branch `update_pre_commit_XXXXXXXXXXXXXXXXXXXXX`.
1. open a pull request against repository default branch.
```
(hello-world) ~/work/hello-world $ update-pre-commit --dry-run false --open-pr true

Starting update-pre-commit on .pre-commit-config.yaml (dry-run False open-pr True)...

hadolint/hadolint (v2.11.0) is not using the latest release rev (v2.12.0)
pycqa/flake8 (7.1.2) is not using the latest release tag (7.2.0)
antonbabenko/pre-commit-terraform (v1.98.0) is not using the latest release rev (v1.99.0)

Update revs in .pre-commit-config.yaml: Success

Checkout new branch successfully....

Push commits successfully:
from local branch: update_pre_commit_01JV8P09N4G5K9Q4DDD533ARBH
with commit hash : 7b293faf5e14f6950bf28b510eb8d8c8beff26fe

Creating a Pull Request as follows:
Owner/Repo.  : tagdots/hello-world
Title        : update pre-commit-config
Source Branch: tagdots:update_pre_commit_01JV8P09N4G5K9Q4DDD533ARBH
PR for Branch: main
Rev Variances: [{"owner_repo": "antonbabenko/pre-commit-terraform", "current_rev": "v1.98.1", "new_rev": "v1.99.0"}, {"owner_repo": "adrienverge/yamllint", "current_rev": "v1.37.0", "new_rev": "v1.37.1"}]

Created pull request #101 successfully: https://github.com/tagdots/hello-world/pull/101
```

<br>

## 😕  Troubleshooting

**Step 1 - Ensure the following**

```
* your project's .pre-commit-config.yaml file is valid.
* your GitHub fine-grained token has the write permissions to contents and pull requests.
* update-pre-commit can find the .pre-commit-config.yaml file at the root of YOUR project.
```

**Step 2 - Open an [issue][issues]**

<br>

## 🙏  Contributing

Pull requests and stars are always welcome.  For pull requests to be accepted on this project, you should follow [PEP8][pep8] when creating/updating Python codes.

See [Contributing][contributing]

<br>

## 📚 References

[Pre-Commit on Github](https://github.com/pre-commit/pre-commit-hooks)

[How to fork a repo](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo)

[Manage Github Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)

<br>

[contributing]: https://github.com/tagdots/update-pre-commit/blob/main/CONTRIBUTING.md
[issues]: https://github.com/tagdots/update-pre-commit/issues
[pep8]: https://google.github.io/styleguide/pyguide.html
