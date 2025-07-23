#!/usr/bin/env python

"""
Purpose: update pre-commit configuration and create a pull request
"""

import json
import os
import sys
import threading
import time

import click
import git
import ulid
import yaml
from github import Auth, Github

from update_pre_commit import __version__


def get_auth():
    """
    Creates an instance of the Github class to interact with GitHub API

    Parameter(s): None

    Return: GitHub Object
    """
    return Github(auth=Auth.Token(os.environ['GH_TOKEN']))


def get_owner_repo(file):
    """
    Create generator to capture owner_repo and current_rev from {file}

    Parameter(s):
    file: .pre-commit-config.yaml (default)

    Return: generator object e.g. ({owner_repo: owner_repo, current_rev: current_rev })
    """
    with open(f'{file}', 'r') as f:
        data = yaml.safe_load(f)
        return ({'owner_repo': '/'.join(r['repo'].rsplit('/', 2)[-2:]).replace('.git', ''),
                'current_rev': r['rev']} for r in data['repos'])


def start_thread(gh, variance_list, gen_repos_revs):  # pragma: no cover
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


def get_rev_variances(gh, variance_list, owner_repo, current_rev):
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

        except Exception as e:
            if f'{e.status}' == "404":
                tag = next(x for x in repo.get_tags() if ("alpha" and "beta" and "prerelease" and "rc") not in x.name)
                if not current_rev == tag.name:
                    print(f'{owner_repo} ({current_rev}) is not using the latest release tag ({tag.name})')
                    add_variance_to_dict(owner_repo, current_rev, tag.name, variance_list)

    except Exception as e:  # pragma: no cover
        if f'{e.status}' == "404":
            print(f'Repository: {owner_repo} not found but we will continue to process the rest.')


def add_variance_to_dict(owner_repo, current_rev, new_rev, variance_list):
    """
    Append rev variances to variance_list

    Parameter(s):
    owner_repo : current github_owner/repository from {file}
    current_rev: current version on {file}
    new_rev    : new rev from get_rev_variances
    """
    variance_dict = {}
    variance_dict.update(owner_repo=owner_repo, current_rev=current_rev, new_rev=new_rev)
    variance_list.append(variance_dict)


def update_pre_commit_config(file, variance_list):
    """
    Load {file} into a Python object
    Update Python object
    Dump Python object into {file}

    Parameter(s):
    file         : .pre-commit-config.yaml (default)
    variance_list: e.g. [{owner_repo: owner_repo, current_rev: current_rev, new_rev: new_rev }]
    """
    with open(file, 'r') as f:
        data = yaml.safe_load(f)

    x = len(data['repos'])
    for i, v in ((i, v) for i in range(x) for v in variance_list):
        if v['owner_repo'] in data['repos'][i]['repo'] and v['current_rev'] in data['repos'][i]['rev']:
            data['repos'][i]['rev'] = v['new_rev']

    with open(file, 'w') as f:
        yaml.dump(data, f, indent=2, sort_keys=False)

    print(f'\nUpdate revs in {file}: Success\n')


def checkout_new_branch():
    """
    Create a git object to checkout a new branch

    Parameter(s): None
    """
    repo_path = os.getcwd()
    branch_suffix = ulid.new()

    try:
        repo_obj = git.Repo(repo_path)
        repo_obj_branch_name = repo_obj.create_head(f'update_pre_commit_{branch_suffix}')
        repo_obj_branch_name.checkout()
        repo_obj_remote_url = repo_obj.remotes.origin.url
        owner_repo = '/'.join(repo_obj_remote_url.rsplit('/', 2)[-2:]).replace('.git', '')
        print('Checkout new branch successfully....\n')
        return owner_repo, repo_obj_branch_name

    except Exception as e:  # pragma: no cover
        print(f'Error: {e}\n')
        return None


def push_commit(file, active_branch_name, msg_suffix):
    """
    Push commits to remote

    Parameter(s):
    file              : .pre-commit-config.yaml (default)
    active_branch_name: from checkout_new_branch
    msg_suffix        : from main (empty except for "coverage run" where [CI-Testing] is the msg_suffix)
    """
    repo_path = os.getcwd()
    branch = active_branch_name
    message = f'update pre-commit-config {msg_suffix}'
    files_to_stage = [file]

    try:
        repo_obj = git.Repo(repo_path)
        repo_obj.index.add(files_to_stage)
        repo_obj.index.write()
        commit = repo_obj.index.commit(message)
        repo_obj.git.push("--set-upstream", 'origin', branch)
        print('Push commits to remote successfully:')
        print(f'from local branch: {branch}')
        print(f'with commit hash : {commit.hexsha}\n')

    except Exception as e:  # pragma: no cover
        print(f'Error: {e}\n')
        return None


def create_pr(gh, owner_repo, active_branch_name, variance_list, msg_suffix):
    """
    Create Pull Request

    Parameter(s):
    gh                : github class object from get_auth()
    owner_repo        : current github_owner/repository from {file}
    active_branch_name: from checkout_new_branch
    variance_list     : e.g. [{owner_repo: owner_repo, current_rev: current_rev, new_rev: new_rev }]
    msg_suffix        : from main (empty except for "coverage run" where [CI-Testing] is the msg_suffix)
    """
    owner = owner_repo.split('/')[0]
    repo = gh.get_repo(owner_repo)
    pr_base_branch = repo.default_branch
    pr_body = json.dumps(variance_list)
    pr_branch = f'{owner}:{active_branch_name}'
    pr_title = f'update pre-commit-config {msg_suffix}'

    print('Creating a Pull Request as follows:')
    print(f'Owner/Repo.  : {owner_repo}')
    print(f'Title        : {pr_title}')
    print(f'Source Branch: {pr_branch}')
    print(f'Target Branch: {pr_base_branch}')
    print(f'Rev Variances: {pr_body}')

    try:
        pr = repo.create_pull(title=pr_title, body=pr_body, head=pr_branch, base=pr_base_branch)
        print(f'\nCreate pull request #{pr.number} successfully: {pr.html_url}\n')
        return pr.number

    except Exception as e:  # pragma: no cover
        print(f'Error: {e}\n')
        return None


@click.command()
@click.option('--file', required=False, default='.pre-commit-config.yaml', help='default: .pre-commit-config.yaml')
@click.option('--dry-run', required=False, default=True, help='default: true')
@click.option('--open-pr', required=False, default=False, help='default: false')
@click.version_option(version=__version__)
def main(file, dry_run, open_pr):
    print(f'Starting update-pre-commit on {file} (dry-run {dry_run} open-pr {open_pr})...\n')
    try:
        cleanup = 10
        variance_list = []
        gh = get_auth()
        gen_repos_revs = get_owner_repo(file)
        start_thread(gh, variance_list, gen_repos_revs)
        msg_suffix = ''

        """
        When coverage.py runs by the "coverage run" command, an environment variable COVERAGE_RUN is created.
        The PR title will have the suffix [CI - Testing] to indicate that it is created from some "coverage run".
        """
        if 'COVERAGE_RUN' in os.environ:
            msg_suffix = '[CI - Testing]'

        if len(variance_list) > 0 and not dry_run:
            update_pre_commit_config(file, variance_list)

            if open_pr:
                owner_repo, active_branch_name = checkout_new_branch()
                push_commit(file, active_branch_name, msg_suffix)
                pr_number = create_pr(gh, owner_repo, active_branch_name, variance_list, msg_suffix)

                if 'COVERAGE_RUN' in os.environ:
                    repo = gh.get_repo(owner_repo)
                    pull = repo.get_pull(pr_number)
                    ref = repo.get_git_ref(f"heads/{active_branch_name}")
                    time.sleep(cleanup)
                    pull.edit(state="closed")
                    ref.delete()
        else:
            print(f'\nUpdate revs in {file}: None\n')

    except Exception:
        print('Error !! Ensure that the pre-commit config file is valid and the token has appropriate permissions.')
        sys.exit(1)


if __name__ == '__main__':  # pragma: no cover
    main()
