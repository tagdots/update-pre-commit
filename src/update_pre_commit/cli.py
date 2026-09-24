"""CLI tool to update pre-commit configuration and optionally create a pull request

This module provides functionality to:
- Read and parse .pre-commit-config.yaml files
- Check GitHub repositories for available updates to commit revisions
- Update local pre-commit configuration with the latest versions
- Optionally create a git branch, commit, push, and open a pull request

Usage:
    update-pre-commit [--file FILE] [--open-pr] [--dry-run]

Options:
    --file     Path to pre-commit config file (default: .pre-commit-config.yaml)
    --open-pr  Create a pull request after updating (default: false)
    --dry-run  Show what would be updated without making changes (default: true)

Environment:
    GH_TOKEN   GitHub personal access token with read/write access for repositories
               and pull requests. Required when using --open-pr.
"""

import json
import os
import sys
import threading
from typing import Any, Generator

import click
import git
import ulid
import yaml
from github import (
    Auth,
    BadCredentialsException,
    Github,
    GithubException,
    Repository,
    UnknownObjectException,
)

from update_pre_commit import __version__

# Tags containing any of these keywords are considered prerelease and will be skipped
PRERELEASE_KEYWORDS = ["alpha", "beta", "prerelease", "pre-release", "rc"]


def get_auth() -> Github:
    """Create and validate a GitHub client instance.

    This function reads the GH_TOKEN environment variable, creates a
    Github client, and verifies the token by calling Github.get_rate_limit.

    Returns:
        A configured Github client instance.

    Raises:
        KeyError: If the GH_TOKEN environment variable is not set.
        PermissionError: If the GitHub token is invalid or has expired.
    """
    try:
        gh_token = os.environ["GH_TOKEN"]
        gh = Github(auth=Auth.Token(gh_token), per_page=100)
        gh.get_rate_limit()
        return gh

    except KeyError:
        raise KeyError("GitHub Token - not found")
    except BadCredentialsException:
        raise PermissionError("GitHub Token - bad credential")


def get_origin_owner_repo() -> str:
    """Get owner/repo from Repo URL

    This function reads the default remote repository (origin) URL.
    e.g.  https://github.com/{user/org}/repo

    Returns:
        owner/repo from default remote repository URL
    """
    repo = git.Repo(os.getcwd())
    repo_remotes_origin_url = repo.remotes.origin.url

    origin_owner_repo = (
        "/".join(repo_remotes_origin_url.rsplit("/", 2)[-2:])
        .replace(".git", "")
        .replace("git@github.com:", "")
        .replace("https://github.com/", "")
    )

    return origin_owner_repo


def get_active_branch_name() -> str:
    """Get the name of the currently active git branch.

    Returns:
        The name of the active branch as a string.

    Raises:
        TypeError: If HEAD is detached (no active branch).
    """
    repo = git.Repo(os.getcwd())

    return repo.active_branch.name


def get_owner_repo_revs(file: str) -> Generator[dict[str, str], None, None]:
    """Create a generator that captures all owner_repo and current_rev from the config file.

    Reads the pre-commit configuration file and extracts repository URLs and their
    current commit revisions for all configured repositories.

    Args:
        file: Path to the pre-commit configuration file (default: .pre-commit-config.yaml)

    Yields:
        Dictionary with 'owner_repo' and 'current_rev' keys for each configured repo.

    Raises:
        FileNotFoundError: If the specified file is not found.
        yaml.YAMLError: If the YAML file cannot be parsed.
    """
    try:
        with open(file, "r") as f:
            data: Any = yaml.safe_load(f)
            return (
                {"owner_repo": "/".join(r["repo"].rsplit("/", 2)[-2:]).replace(".git", ""), "current_rev": r["rev"]}
                for r in data["repos"]
            )
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found - {file}")
    except yaml.YAMLError:
        raise yaml.YAMLError(f"Failed to parse YAML file - {file}")


def start_thread(gh: Github, variance_list: list, gen_repos_revs) -> None:  # pragma: no cover
    """Create threads to enable concurrent execution within a single process.

    Spawns multiple threads to fetch repository revision data concurrently,
    improving performance when checking multiple repositories.

    Args:
        gh: GitHub client instance.
        variance_list: List to populate with repository variance data.
        gen_repos_revs: Generator yielding dictionaries with 'owner_repo' and 'current_rev'.

    Returns:
        None
    """
    threads = []
    for r in gen_repos_revs:
        thread = threading.Thread(
            target=get_rev_variances,
            args=(
                gh,
                variance_list,
                r["owner_repo"],
                r["current_rev"],
            ),
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()


def get_rev_variances(gh: Github, variance_list: list, owner_repo: str, current_rev: str) -> None:
    """Fetch the latest revision for a repository and compare with current version.

    Attempts to get the latest release first, and if not available, falls back to
    getting the latest tag that is not a prerelease. Adds variance to the list
    if the current revision is outdated.

    Args:
        gh: GitHub client instance.
        variance_list: List to append variance data if update is needed.
        owner_repo: Repository identifier in 'owner/repo' format.
        current_rev: Current revision from the pre-commit config file.
    """
    try:
        repo = gh.get_repo(owner_repo)
        try:
            latest_release = repo.get_latest_release()

            if not current_rev == latest_release.tag_name:
                print(f"{owner_repo} ({current_rev}) is not using the latest release rev ({latest_release.tag_name})")
                add_variance_to_dict(owner_repo, current_rev, latest_release.tag_name, variance_list)

        except UnknownObjectException as e:
            if f"{e.status}" == "404":
                tag = next(x for x in repo.get_tags() if not any(kw in x.name for kw in PRERELEASE_KEYWORDS))
                if not current_rev == tag.name:
                    print(f"{owner_repo} ({current_rev}) is not using the latest release tag ({tag.name})")
                    add_variance_to_dict(owner_repo, current_rev, tag.name, variance_list)

    except UnknownObjectException as e:
        if f"{e.status}" == "404":
            print(f"❌ {owner_repo} repository not found")


def add_variance_to_dict(owner_repo: str, current_rev: str, new_rev: str, variance_list: list) -> None:
    """Add a repository revision variance to the variance list.

    Creates a variance dictionary with the old and new revisions and appends
    it to the provided list for later processing.

    Args:
        owner_repo: Repository identifier in 'owner/repo' format.
        current_rev: Current revision from the pre-commit config file.
        new_rev: New revision that should replace the current one.
        variance_list: List to append the variance dictionary to.
    """
    variance_dict = {}
    variance_dict.update(owner_repo=owner_repo, current_rev=current_rev, new_rev=new_rev)
    variance_list.append(variance_dict)


def update_pre_commit_config(file: str, variance_list: list) -> None:
    """Update the pre-commit config file with new revisions.

    Loads the pre-commit configuration, updates repository revisions based on
    the variance list, and writes the changes back to the file.

    Args:
        file: Path to the pre-commit configuration file.
        variance_list: List of dictionaries containing owner_repo, current_rev, and new_rev.
    """
    # Return type of the PyYAML loading function can be Any or generic dict without specific key/value types
    with open(file, "r") as f:
        data: Any = yaml.safe_load(f)

    number_of_repos = len(data["repos"])
    for index, variance in ((index, variance) for index in range(number_of_repos) for variance in variance_list):
        if variance["owner_repo"] in data["repos"][index]["repo"] and variance["current_rev"] in data["repos"][index]["rev"]:
            data["repos"][index]["rev"] = variance["new_rev"]

    with open(file, "w") as f:
        yaml.dump(data, f, indent=2, sort_keys=False)

    print(f"\n✅ Update revs in {file}: Success")


def checkout_new_branch() -> str:
    """Create and checkout a new git branch with a unique suffix.

    Generates a new branch name using a ULID suffix and creates a new branch
    from the current HEAD, then switches to that branch.

    Returns:
        The name of the newly created branch.
    """
    branch_suffix = ulid.new()
    new_local_branch_name = f"dep/update_pre_commit_{branch_suffix}"

    # Create a Repository Object from current path (os.getcwd())
    repo = git.Repo(os.getcwd())

    # Use Repository Object to create a new branch pointing to the current HEAD
    # Switch working tree and HEAD to point to that branch.
    new_local_branch = repo.create_head(new_local_branch_name)
    new_local_branch.checkout()

    print(f"✅ Checkout new branch ({new_local_branch_name}).")

    return new_local_branch_name


def push_commit(file: str, new_local_branch_name: str) -> None:
    """Commit the config file changes and push to remote branch.

    Stages the specified file, commits it with a standard message,
    and pushes the branch to the remote repository.

    Args:
        file: Path to the pre-commit configuration file that was updated.
        new_local_branch_name: Name of the branch to push to remote.
    """
    message = "update pre-commit-config"
    files_to_stage = [file]

    # Create a Repository Object from current path (os.getcwd())
    repo = git.Repo(os.getcwd())

    # Use Repository Object to stage and commit
    repo.index.add(files_to_stage)
    repo.index.write()
    repo.index.commit(message)

    # Push to remote (git push)
    origin = repo.remote(name="origin")
    origin.push(refspec=f"{new_local_branch_name}:{new_local_branch_name}")

    print(f"✅ Push commits to remote from local branch: {new_local_branch_name}")


def create_pr(
    gh_repo: Repository.Repository, owner_repo: str, new_local_branch_name: str, variance_list: list
) -> int | None:
    """Create a pull request on GitHub for the updated configuration.

    Creates a new pull request with the branch containing the updated
    pre-commit configuration. The PR body contains the revision variances
    as a JSON summary.

    Args:
        gh_repo: GitHub repository object.
        owner_repo: Repository identifier in 'owner/repo' format.
        new_local_branch_name: Name of the branch to create the PR from.
        variance_list: List of revision variance dictionaries.

    Returns:
        The PR number if successful, None if creation failed.
    """
    try:
        # Retrieve owner from owner_repo
        owner = owner_repo.split("/")[0]

        # Use GitHub repository object to create PR
        pr_base_branch = gh_repo.default_branch
        pr_body = json.dumps(variance_list)
        pr_branch = f"{owner}:{new_local_branch_name}"
        pr_title = "update pre-commit-config"
        pr = gh_repo.create_pull(title=pr_title, body=pr_body, head=pr_branch, base=pr_base_branch)

        return pr.number

    except GithubException as err:
        print(f"❌ Error creating pull request: {err.status} - {err.data}")
        return None


@click.command()
@click.option(
    "--file",
    required=False,
    default=".pre-commit-config.yaml",
    help="Path to pre-commit config file (default: .pre-commit-config.yaml)",
)
@click.option(
    "--dry-run", required=False, default=True, help="Show what would be updated without making changes (default: true)"
)
@click.option("--open-pr", required=False, default=False, help="Create a pull request after updating (default: false)")
@click.version_option(version=__version__)
def main(file, dry_run, open_pr):
    """Update pre-commit configuration and optionally create a pull request.

    This command reads the pre-commit configuration file, checks all configured
    repositories for available updates to their commit revisions, and updates
    the file with the latest versions.

    When --open-pr is used, creates a new branch, commits the changes, pushes
    to remote, and opens a pull request on GitHub.
    """
    print(f"🚀 Starting update-pre-commit (ver.: {__version__}, file: {file}, dry-run: {dry_run}, open-pr: {open_pr})...\n")
    try:
        origin_owner_repo = get_origin_owner_repo()
        original_active_branch_name = get_active_branch_name()

        # Create a GitHub client instance and get the repository object
        gh = get_auth()
        gh_repo = gh.get_repo(origin_owner_repo)

        variance_list = []
        gen_repos_revs = get_owner_repo_revs(file)

        # Concurrently fetch current vs latest revisions for all configured repos
        start_thread(gh, variance_list, gen_repos_revs)

        # Proceed with updates if there are variance to apply and not in dry-run mode
        if len(variance_list) > 0 and not dry_run:
            update_pre_commit_config(file, variance_list)

            if open_pr:
                # Use GitPython to create commit and push branch
                new_local_branch_name = checkout_new_branch()
                push_commit(file, new_local_branch_name)

                # Use pyGitHub client to create PR
                pr_number = create_pr(gh_repo, origin_owner_repo, new_local_branch_name, variance_list)

                # Restore to original active branch name
                git_repo = git.Repo(os.getcwd())
                local_branch = git_repo.heads[original_active_branch_name]
                local_branch.checkout()
                print(f"✅ Pull request created successfully : https://github.com/{origin_owner_repo}/pull/{pr_number}")
                print(f"✅ Branch restored to original branch: {original_active_branch_name}")

        else:
            print(f"\n✅ Update revs in {file}: None")

    except Exception as err:
        print(f"❌ Exception: {err}") if err else print("❌ Unexpected Exception Error")
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
