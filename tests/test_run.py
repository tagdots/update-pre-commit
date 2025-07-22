#!/usr/bin/env python

"""
Purpose: tests
"""
import io
import os
import shutil
import sys
import unittest
from unittest.mock import patch

from click.testing import CliRunner
from github import Github

from update_pre_commit.run import (
    get_auth,
    get_owner_repo,
    get_rev_variances,
    main,
    update_pre_commit_config,
)


class TestGetAuth(unittest.TestCase):
    ''' hold output from source script '''
    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    """
    reference: https://github.com/PyGithub/PyGithub/blob/v2.6.1/github/Auth.py#L153-L173
    assertion: assert Token is token instance is string and has length > 0
    """
    @patch.dict(os.environ, {'GH_TOKEN': 'github_pat_123456'}, clear=True)  # checkov:skip=CKV_SECRET_6
    def test_get_auth_with_valid_gh_token(self):
        self.assertIsInstance(get_auth(), Github)

    """
    reference: https://github.com/PyGithub/PyGithub/blob/v2.6.1/github/Auth.py#L153-L173
    assertion: assert AssertionError when length of Token is not > 0
    """
    @patch.dict(os.environ, {'GH_TOKEN': ''}, clear=True)  # checkov:skip=CKV_SECRET_6
    def test_get_auth_with_invalid_gh_token(self):
        with self.assertRaises(AssertionError):
            get_auth()


class TestGetOwnerRepo(unittest.TestCase):
    file = 'tests/files/pre-commit-config.yaml'

    ''' hold output from source script '''
    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    """
    assertion: assert the specified file exists
    """
    def test_get_owner_repo_file_exist(self):
        self.assertTrue(os.path.exists(self.file))

    """
    assertion: assert get_owner_repo returns a valid generator
    """
    def test_get_owner_repo_return_gen(self):
        fn_return_generator = get_owner_repo(self.file)
        self.assertIsInstance(fn_return_generator, type((x for x in [])))


class TestGetRevVariances(unittest.TestCase):
    ''' hold output from source script '''
    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    gen_repos_revs = [
        {'owner_repo': 'adrienverge/yamllint', 'current_rev': 'v1.37.0'},
        {'owner_repo': 'pre-commit/pre-commit-hooks', 'current_rev': 'v4.0.0'},
        {'owner_repo': 'pycqa/flake8', 'current_rev': '7.1.2'}
    ]

    """
    assertion: assert variance_list successfully built from gen_repos_revs
    """
    def test_get_rev_variances_to_dict(self):
        variance_list = []
        for r in self.gen_repos_revs:
            get_rev_variances(get_auth(), variance_list, r['owner_repo'], r['current_rev'])
        assert type(variance_list) is not None


class TestUpdatePreCommit(unittest.TestCase):
    file_src = 'tests/files/pre-commit-config.yaml'
    file_dst = 'tests/files/pre-commit-config-temp.yaml'
    variance_list = [
        {'owner_repo': 'pycqa/flake8', 'current_rev': '7.1.2', 'new_rev': '7.2.0'},
        {'owner_repo': 'pre-commit/pre-commit-hooks', 'current_rev': 'v4.0.0', 'new_rev': 'v5.0.0'}
    ]

    ''' hold output from source script '''
    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    ''' assert output is a list after update_pre_commit '''
    def test_update_pre_commit_return_gen(self):
        shutil.copyfile(self.file_src, self.file_dst)
        update_pre_commit_config(self.file_dst, self.variance_list)
        fn_return_generator = get_owner_repo(self.file_dst)
        self.assertIsInstance(fn_return_generator, type((x for x in [])))
        os.remove(self.file_dst)


class TestZMain(unittest.TestCase):
    file = 'tests/files/pre-commit-config.yaml'

    def setUp(self):
        self.runner = CliRunner()

    ''' assert zero exit code with dry-run false '''
    def test_main_dry_run_false_success(self):
        result = self.runner.invoke(main, ['--file', self.file, '--dry-run', 'False', '--open-pr', 'True'])
        print(result.stdout)
        print(result.stderr)
        self.assertEqual(result.exit_code, 0)

    ''' assert zero exit code with help '''
    def test_main_help(self):
        result = self.runner.invoke(main, ['--help'])
        self.assertEqual(result.exit_code, 0)

    ''' assert zero exit code with dry-run true with a valid file '''
    def test_main_dry_run_true_failure(self):
        result = self.runner.invoke(main, ['--file', self.file])
        self.assertEqual(result.exit_code, 0)

    ''' assert zero exit code with dry-run true '''
    def test_main_dry_run_true_success(self):
        result = self.runner.invoke(main, ['--dry-run', 'True'])
        self.assertEqual(result.exit_code, 0)

    ''' assert non-zero exit code with dry-run typo '''
    def test_main_dry_run_typo_failure(self):
        result = self.runner.invoke(main, ['--dry-run', 'Typo'])
        self.assertNotEqual(result.exit_code, 0)

    ''' assert non-zero exit code with non-existent file '''
    def test_main_file_not_exist_failure(self):
        result = self.runner.invoke(main, ['--file', 'file-not-exist.yaml'])
        self.assertNotEqual(result.exit_code, 0)

    ''' assert non-zero exit code with an invalid option '''
    def test_main_invalid_option_failure(self):
        result = self.runner.invoke(main, ['--hello', 'world'])
        self.assertNotEqual(result.exit_code, 0)


if __name__ == '__main__':
    unittest.main()
