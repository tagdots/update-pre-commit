#!/usr/bin/env python

"""
Purpose: update pre-commit configuration and optionally create a pull request
"""

import json
import os
import sys
import threading
import time
from typing import Any, Tuple

import click
import git
import ulid
import yaml
from github import (
    Auth,
    BadCredentialsException,
    Github,
    GithubException,
    UnknownObjectException,
)

from update_pre_commit import __version__


TAG_NAME = "('alpha' and 'beta' and 'prerelease' and 'pre-release' and 'rc')"


def get_auth() -> Github:
    """
    Creates an instance of the Github class to interact with GitHub API
    """
    try:
        gh_token = os.environ['GH_TOKEN']
        gh = Github(auth=Auth.Token(gh_token), per_page=100)
        gh.get_rate_limit()
        return gh

    except KeyError:
        raise KeyError('GH_TOKEN (environment variable) not found')
    except BadCredentialsException:
        raise PermissionError('Invalid GitHub Token (GH_TOKEN)')


def get_owner_repo(file: str):
    """
    Create generator to capture ALL owner_repo and current_rev from {file}

    Parameter(s):
    file: .pre-commit-config.yaml (default)

    Return: generator object e.g. ({owner_repo: owner_repo, current_rev: current_rev })
    Note  : the return type of the PyYAML loading function can be Any or a generic dict without specific key/value types
    """
    try:
        with open(f'{file}', 'r') as f:
            data: Any = yaml.safe_load(f)
            return ({'owner_repo': '/'.join(r['repo'].rsplit('/', 2)[-2:]).replace('.git', ''),
                     'current_rev': r['rev']} for r in data['repos'])
    except FileNotFoundError:
        raise FileNotFoundError(f'File not found - {file}')
    except yaml.YAMLError:
        raise yaml.YAMLError(f'Failed to parse YAML file - {file}')


def start_thread(gh: Github, variance_list: list, gen_repos_revs):  # pragma: no cover
    """
    Create threads to enable concurrent execution within a single process

    Parameter(s):
    gh            : github class object from get_auth()
    variance_list : empty list
    gen_repos_revs: class generator to iterate
    """
    threads = []
    for r in gen_repos_revs:
        thread = threading.Thread(target=get_rev_variances, args=(gh, variance_list, r['owner_repo'], r['current_rev'],))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()


def get_rev_variances(gh: Github, variance_list: list, owner_repo: str, current_rev: str):
    """
    Create Repository object and use get_latest_release or get_tags methods to obtain the latest rev or tag.
    Call add_variance_to_dict function to build variance_list.

    Parameter(s):
    gh           : github class object from get_auth()
    variance_list: empty list
    owner_repo   : current github_owner/repository from {file}
    current_rev  : current version on {file}
    """
    try:
        repo = gh.get_repo(owner_repo)
        try:
            latest_release = repo.get_latest_release()

            if not current_rev == latest_release.tag_name:
                print(f'{owner_repo} ({current_rev}) is not using the latest release rev ({latest_release.tag_name})')
                add_variance_to_dict(owner_repo, current_rev, latest_release.tag_name, variance_list)

        except UnknownObjectException as e:
            if f'{e.status}' == '404':
                tag = next(x for x in repo.get_tags() if TAG_NAME not in x.name)
                if not current_rev == tag.name:
                    print(f'{owner_repo} ({current_rev}) is not using the latest release tag ({tag.name})')
                    add_variance_to_dict(owner_repo, current_rev, tag.name, variance_list)

    except UnknownObjectException as e:
        if f'{e.status}' == '404':
            print(f'{owner_repo} repository not found')


def add_variance_to_dict(owner_repo: str, current_rev: str, new_rev: str, variance_list: list):
    """
    Append rev variances to variance_list

    Parameter(s):
    owner_repo   : current github_owner/repository from {file}
    current_rev  : current version on {file}
    new_rev      : new rev from get_rev_variances
    variance_list: list to collect rev variance
    """
    variance_dict = {}
    variance_dict.update(owner_repo=owner_repo, current_rev=current_rev, new_rev=new_rev)
    variance_list.append(variance_dict)


def update_pre_commit_config(file: str, variance_list: list):
    """
    Load {file} into a Python object, Update Python object, Dump Python object into {file}
    No try-except here because the yaml file load has been validated in get_owner_repo

    Parameter(s):
    file         : .pre-commit-config.yaml (default)
    variance_list: e.g. [{owner_repo: owner_repo, current_rev: current_rev, new_rev: new_rev }]
    """
    with open(file, 'r') as f:
        data: Any = yaml.safe_load(f)

    number_of_repos = len(data['repos'])
    for index, variance in ((index, variance) for index in range(number_of_repos) for variance in variance_list):
        if variance['owner_repo'] in data['repos'][index]['repo'] and variance['current_rev'] in data['repos'][index]['rev']:
            data['repos'][index]['rev'] = variance['new_rev']

    with open(file, 'w') as f:
        yaml.dump(data, f, indent=2, sort_keys=False)

    print(f'\nUpdate revs in {file}: Success\n')


def checkout_new_branch() -> Tuple[str, str]:
    """
    Create a git object to checkout a new branch
    """
    branch_suffix = ulid.new()
    new_local_branch_name = f'dep/update_pre_commit_{branch_suffix}'

    repo = git.Repo(os.getcwd())
    repo_head_obj = repo.create_head(new_local_branch_name)
    repo_head_obj.checkout()
    repo_remotes_origin_url = repo.remotes.origin.url
    owner_repo = '/'.join(repo_remotes_origin_url.rsplit('/', 2)[-2:]).\
        replace('.git', '').replace('git@github.com:', '').replace('https://github.com/', '')
    print(f'Checkout new branch ({new_local_branch_name}) successfully....\n')

    return (owner_repo, new_local_branch_name)


def push_commit(file: str, new_local_branch_name: str, msg_suffix: str):
    """
    Push commits to remote

    Parameter(s):
    file                 : .pre-commit-config.yaml (default)
    new_local_branch_name: from checkout_new_branch
    msg_suffix           : from main (empty except for "coverage run" where [CI-Testing] is the msg_suffix)
    """
    branch = new_local_branch_name
    message = f'update pre-commit-config {msg_suffix}'
    files_to_stage = [file]

    repo = git.Repo(os.getcwd())
    repo.index.add(files_to_stage)
    repo.index.write()
    commit = repo.index.commit(message)
    repo.git.push("--set-upstream", 'origin', branch)
    print('Push commits to remote successfully:')
    print(f'from local branch: {branch}')
    print(f'with commit hash : {commit.hexsha}\n')


def create_pr(gh: Github, owner_repo: str, new_local_branch_name: str, variance_list: list, msg_suffix: str) -> int | None:
    """
    Create Pull Request

    Parameter(s):
    gh                   : github class object from get_auth()
    owner_repo           : current github_owner/repository from {file}
    new_local_branch_name: from checkout_new_branch
    variance_list        : e.g. [{owner_repo: owner_repo, current_rev: current_rev, new_rev: new_rev }]
    msg_suffix           : from main (empty except for "coverage run" where [CI-Testing] is the msg_suffix)
    """
    try:
        owner = owner_repo.split('/')[0]
        repo = gh.get_repo(owner_repo)
        pr_base_branch = repo.default_branch
        pr_body = json.dumps(variance_list)
        pr_branch = f'{owner}:{new_local_branch_name}'
        pr_title = f'update pre-commit-config {msg_suffix}'

        print('Creating a Pull Request as follows:')
        print(f'Owner/Repo.  : {owner_repo}')
        print(f'Title        : {pr_title}')
        print(f'Source Branch: {pr_branch}')
        print(f'Target Branch: {pr_base_branch}')
        print(f'Rev Variances: {pr_body}')
        pr = repo.create_pull(title=pr_title, body=pr_body, head=pr_branch, base=pr_base_branch)
        print(f'\nCreate pull request #{pr.number} successfully: {pr.html_url}\n')
        return pr.number

    except GithubException as err:
        print(f"Error creating pull request: {err.status} - {err.data}")
        return None


@click.command()
@click.option('--file', required=False, default='.pre-commit-config.yaml', help='default: .pre-commit-config.yaml')
@click.option('--dry-run', required=False, default=True, help='default: true')
@click.option('--open-pr', required=False, default=False, help='default: false')
@click.version_option(version=__version__)
def main(file, dry_run, open_pr):
    print(f'Starting update-pre-commit (file: {file}, dry-run: {dry_run}, open-pr: {open_pr})...\n')
    try:
        cleanup = 10
        variance_list = []
        gh = get_auth()
        gen_repos_revs = get_owner_repo(file)
        start_thread(gh, variance_list, gen_repos_revs)

        """
        When coverage.py runs by the "coverage run" command, an environment variable COVERAGE_RUN is created.
        The PR title will have the suffix [CI - Testing] to indicate that it is created from some "coverage run".
        """
        msg_suffix = '[CI - Testing]' if 'COVERAGE_RUN' in os.environ else ''
        if len(variance_list) > 0 and not dry_run:
            update_pre_commit_config(file, variance_list)

            if open_pr:
                owner_repo, new_local_branch_name = checkout_new_branch()
                push_commit(file, new_local_branch_name, msg_suffix)
                pr_number = create_pr(gh, owner_repo, new_local_branch_name, variance_list, msg_suffix)

                if 'COVERAGE_RUN' in os.environ and pr_number is not None:
                    repo = gh.get_repo(owner_repo)
                    pull = repo.get_pull(pr_number)
                    ref = repo.get_git_ref(f"heads/{new_local_branch_name}")
                    time.sleep(cleanup)
                    pull.edit(state="closed")
                    ref.delete()
        else:
            print(f'\nUpdate revs in {file}: None\n')

    except Exception as err:
        print(f'Error: {err}\n')
        sys.exit(1)


if __name__ == '__main__':  # pragma: no cover
    main()
