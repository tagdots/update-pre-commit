"""
Unit tests

This module provides comprehensive test coverage for the CLI functionality
including authentication, repository operations, version variance detection,
and pull request creation.

Test Coverage:
- TestGetAuth: GitHub authentication (valid/invalid tokens, permissions)
- TestGetOwnerRepoRevs: YAML file parsing and repository version retrieval
- TestGetOriginOwnerRepo: GitHub URL parsing (HTTPS/SSH formats)
- TestGetActiveBranchName: Git branch detection
- TestGetRevVariances: Version variance detection with GitHub API integration
- TestAddVarianceToDict: Variance list management
- TestCheckoutNewBranch: Git branch creation with ULID
- TestPushCommit: Git commit and push operations
- TestCreatePr: Pull request creation
- TestUpdatePreCommit: Pre-commit config file updates
- TestZMain: Integration tests for main CLI command
"""

import io
import os
import shutil
import sys
import unittest
from unittest.mock import (
    Mock,
    patch,
)

import yaml
from click.testing import CliRunner

from update_pre_commit.cli import (
    add_variance_to_dict,
    checkout_new_branch,
    create_pr,
    get_active_branch_name,
    get_auth,
    get_origin_owner_repo,
    get_owner_repo_revs,
    get_rev_variances,
    main,
    push_commit,
    update_pre_commit_config,
)


class TestGetAuth(unittest.TestCase):
    """Test get_auth function for GitHub authentication"""

    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def test_get_auth_with_no_gh_token(self):
        """Assert KeyError is raised when GH_TOKEN environment variable is not set"""
        with self.assertRaises(KeyError):
            with patch.dict(os.environ, {}, clear=True):
                get_auth()

    @patch("update_pre_commit.cli.Github")
    @patch.dict(os.environ, {"GH_TOKEN": "invalid_token"}, clear=True)  # checkov:skip=CKV_SECRET_6
    def test_get_auth_with_bad_credentials(self, mock_github):
        """Assert PermissionError is raised when GitHub token has invalid credentials (BadCredentialsException)"""
        from github import BadCredentialsException

        mock_github.return_value.get_rate_limit.side_effect = BadCredentialsException(401, "Bad credentials")
        with self.assertRaises(PermissionError):
            get_auth()

    @patch("update_pre_commit.cli.Github")
    @patch.dict(os.environ, {"GH_TOKEN": "valid_token"}, clear=True)  # checkov:skip=CKV_SECRET_6
    def test_get_auth_with_valid_token(self, mock_github):
        """Assert get_auth returns GitHub client instance when token is valid"""
        mock_gh = Mock()
        mock_github.return_value = mock_gh
        result = get_auth()
        self.assertEqual(result, mock_gh)

    @patch("update_pre_commit.cli.Github")
    @patch.dict(os.environ, {"GH_TOKEN": "no_permission"}, clear=True)  # checkov:skip=CKV_SECRET_6
    def test_get_auth_with_non_bad_credentials_exception(self, mock_github):
        """Assert other exceptions propagate when GitHub token fails with non-BadCredentialsException error"""
        mock_github.return_value.get_rate_limit.side_effect = Exception("Network error")
        with self.assertRaises(Exception):
            get_auth()


class TestGetOwnerRepoRevs(unittest.TestCase):
    """Test get_owner_repo_revs function for parsing pre-commit config YAML"""

    file = "tests/files/pre-commit-config.yaml"

    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def test_get_owner_repo_file_exist(self):
        """Assert the pre-commit config file exists"""
        self.assertTrue(os.path.exists(self.file))

    def test_get_owner_repo_return_gen(self):
        """Assert get_owner_repo_revs returns a generator"""
        fn_return_generator = get_owner_repo_revs(self.file)
        self.assertIsInstance(fn_return_generator, type((x for x in [])))

    def test_get_owner_repo_file_not_found(self):
        """Assert FileNotFoundError is raised when file does not exist"""
        with self.assertRaises(FileNotFoundError):
            get_owner_repo_revs("nonexistent.yaml")

    def test_get_owner_repo_invalid_yaml(self):
        """Assert yaml.YAMLError is raised for invalid YAML"""
        with self.assertRaises(yaml.YAMLError):
            get_owner_repo_revs("tests/files/invalid-yaml.yaml")


class TestGetOriginOwnerRepo(unittest.TestCase):
    """Test get_origin_owner_repo function for parsing GitHub repository URLs"""

    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    @patch("update_pre_commit.cli.git.Repo")
    def test_get_origin_owner_repo_https(self, mock_repo):
        """Assert HTTPS GitHub URLs are correctly parsed to owner/repo format"""
        mock_repo_instance = Mock()
        mock_repo_instance.remotes.origin.url = "https://github.com/owner/repo.git"
        mock_repo.return_value = mock_repo_instance
        result = get_origin_owner_repo()
        self.assertEqual(result, "owner/repo")

    @patch("update_pre_commit.cli.git.Repo")
    def test_get_origin_owner_repo_ssh(self, mock_repo):
        """Assert SSH GitHub URLs are correctly parsed to owner/repo format"""
        mock_repo_instance = Mock()
        mock_repo_instance.remotes.origin.url = "git@github.com:owner/repo.git"
        mock_repo.return_value = mock_repo_instance
        result = get_origin_owner_repo()
        self.assertEqual(result, "owner/repo")


class TestGetActiveBranchName(unittest.TestCase):
    """Test get_active_branch_name function"""

    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    @patch("update_pre_commit.cli.git.Repo")
    def test_get_active_branch_name(self, mock_repo):
        """Assert get_active_branch_name returns the correct branch name from git repo"""
        mock_repo_instance = Mock()
        mock_active_branch = Mock()
        mock_active_branch.name = "main"
        mock_repo_instance.active_branch = mock_active_branch
        mock_repo.return_value = mock_repo_instance
        result = get_active_branch_name()
        self.assertEqual(result, "main")


class TestGetRevVariances(unittest.TestCase):
    """Test get_rev_variances function for detecting version variances from GitHub"""

    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    gen_repos_revs = [
        {"owner_repo": "adrienverge/yamllint", "current_rev": "v1.37.0"},
        {"owner_repo": "pre-commit/pre-commit-hooks", "current_rev": "v4.0.0"},
        {"owner_repo": "pycqa/flake8", "current_rev": "7.1.2"},
    ]

    @patch("update_pre_commit.cli.Github")
    def test_get_rev_variances_to_dict(self, mock_github):
        """Assert variance_list is successfully built when GitHub release has newer version"""
        mock_gh = Mock()
        mock_repo = Mock()
        mock_release = Mock()
        mock_release.tag_name = "v1.38.0"
        mock_repo.get_latest_release.return_value = mock_release
        mock_gh.get_repo.return_value = mock_repo
        variance_list = []
        get_rev_variances(mock_gh, variance_list, "adrienverge/yamllint", "v1.37.0")
        self.assertEqual(len(variance_list), 1)
        self.assertEqual(variance_list[0]["owner_repo"], "adrienverge/yamllint")

    @patch("update_pre_commit.cli.Github")
    def test_get_rev_variances_no_update_needed(self, mock_github):
        """Assert no variance is added when current version matches the latest release"""
        mock_gh = Mock()
        mock_repo = Mock()
        mock_release = Mock()
        mock_release.tag_name = "v1.37.0"
        mock_repo.get_latest_release.return_value = mock_release
        mock_gh.get_repo.return_value = mock_repo
        variance_list = []
        get_rev_variances(mock_gh, variance_list, "adrienverge/yamllint", "v1.37.0")
        self.assertEqual(len(variance_list), 0)

    @patch("update_pre_commit.cli.Github")
    def test_get_rev_variances_unknown_object_exception_404_with_tags_no_update_needed(self, mock_github):
        """Assert no variance when using tags fallback and current version matches the tag"""
        from github import UnknownObjectException

        mock_gh = Mock()
        mock_repo = Mock()
        mock_release = Mock()
        mock_release.tag_name = "v1.38.0"
        mock_repo.get_latest_release.side_effect = UnknownObjectException(404, "not found")
        mock_tag1 = Mock()
        mock_tag1.name = "v1.37.0"
        mock_tag2 = Mock()
        mock_tag2.name = "v1.37.0-alpha"
        mock_repo.get_tags.return_value = [mock_tag1, mock_tag2]
        mock_gh.get_repo.return_value = mock_repo
        variance_list = []
        get_rev_variances(mock_gh, variance_list, "adrienverge/yamllint", "v1.37.0")
        self.assertEqual(len(variance_list), 0)

    @patch("update_pre_commit.cli.Github")
    def test_get_rev_variances_unknown_object_exception_404_with_tags_update_needed(self, mock_github):
        """Assert variance is detected when tags fallback shows newer version (404 with tags without alpha/beta)"""
        from github import UnknownObjectException

        mock_gh = Mock()
        mock_repo = Mock()
        mock_release = Mock()
        mock_release.tag_name = "v1.38.0"
        mock_repo.get_latest_release.side_effect = UnknownObjectException(404, "not found")
        mock_tag1 = Mock()
        mock_tag1.name = "v1.40.0"
        mock_tag2 = Mock()
        mock_tag2.name = "v1.41.0"
        mock_repo.get_tags.return_value = [mock_tag1, mock_tag2]
        mock_gh.get_repo.return_value = mock_repo
        variance_list = []
        get_rev_variances(mock_gh, variance_list, "adrienverge/yamllint", "v1.37.0")
        self.assertEqual(len(variance_list), 1)
        self.assertEqual(variance_list[0]["new_rev"], "v1.40.0")

    @patch("update_pre_commit.cli.Github")
    def test_get_rev_variances_repository_not_found_404(self, mock_github):
        """Assert no variance when repository is not found (404)"""
        from github import UnknownObjectException

        mock_gh = Mock()
        mock_gh.get_repo.side_effect = UnknownObjectException(404, "not found")
        variance_list = []
        get_rev_variances(mock_gh, variance_list, "nonexistent/repo", "v1.0.0")
        self.assertEqual(len(variance_list), 0)

    @patch("update_pre_commit.cli.Github")
    def test_get_rev_variances_repository_not_found_non_404(self, mock_github):
        """Assert no variance when repository access fails with non-404 error"""
        from github import UnknownObjectException

        mock_gh = Mock()
        mock_gh.get_repo.side_effect = UnknownObjectException(403, "Forbidden")
        variance_list = []
        get_rev_variances(mock_gh, variance_list, "nonexistent/repo", "v1.0.0")
        self.assertEqual(len(variance_list), 0)

    @patch("update_pre_commit.cli.Github")
    def test_get_rev_variances_unknown_object_exception_non_404(self, mock_github):
        """Assert no variance when getting latest release fails with non-404 error"""
        from github import UnknownObjectException

        mock_gh = Mock()
        mock_repo = Mock()
        mock_repo.get_latest_release.side_effect = UnknownObjectException(403, "Forbidden")
        mock_gh.get_repo.return_value = mock_repo
        variance_list = []
        get_rev_variances(mock_gh, variance_list, "test/repo", "v1.0.0")
        self.assertEqual(len(variance_list), 0)


class TestAddVarianceToDict(unittest.TestCase):
    """Test add_variance_to_dict function"""

    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def test_add_variance_to_dict(self):
        """Assert variance dictionary is correctly added to the variance list"""
        variance_list = []
        add_variance_to_dict("owner/repo", "v1.0.0", "v2.0.0", variance_list)
        self.assertEqual(len(variance_list), 1)
        self.assertEqual(variance_list[0]["owner_repo"], "owner/repo")
        self.assertEqual(variance_list[0]["current_rev"], "v1.0.0")
        self.assertEqual(variance_list[0]["new_rev"], "v2.0.0")

    def test_add_variance_to_dict_multiple(self):
        """Assert multiple variance dictionaries can be added to the list"""
        variance_list = []
        add_variance_to_dict("owner1/repo1", "v1.0.0", "v2.0.0", variance_list)
        add_variance_to_dict("owner2/repo2", "v1.0.0", "v2.0.0", variance_list)
        self.assertEqual(len(variance_list), 2)


class TestCheckoutNewBranch(unittest.TestCase):
    """Test checkout_new_branch function for creating feature branches with ULID"""

    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def test_checkout_new_branch(self):
        """Assert checkout_new_branch creates a branch with correct ULID format"""
        mock_repo_instance = Mock()
        mock_new_branch = Mock()
        mock_repo_instance.create_head.return_value = mock_new_branch
        with patch("update_pre_commit.cli.git.Repo", return_value=mock_repo_instance):
            result = checkout_new_branch()
            self.assertIn("dep/update_pre_commit_", result)
            self.assertEqual(len(result), len("dep/update_pre_commit_") + 26)


class TestPushCommit(unittest.TestCase):
    """Test push_commit function for committing and pushing pre-commit config changes"""

    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    @patch("update_pre_commit.cli.git.Repo")
    def test_push_commit(self, mock_repo):
        """Assert push_commit commits changes and pushes to remote repository"""
        mock_repo_instance = Mock()
        mock_index = Mock()
        mock_commit = Mock()
        mock_commit.hexsha = "abc123def456"
        mock_index.commit.return_value = mock_commit
        mock_repo_instance.index = mock_index
        mock_origin = Mock()
        mock_repo_instance.remote.return_value = mock_origin
        mock_repo.return_value = mock_repo_instance
        push_commit("tests/files/pre-commit-config.yaml", "test-branch")
        mock_origin.push.assert_called_once()


class TestCreatePr(unittest.TestCase):
    """Test create_pr function for creating pull requests on GitHub"""

    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def test_create_pr_success(self):
        """Assert create_pr returns PR number on successful creation"""
        mock_repo = Mock()
        mock_pr = Mock()
        mock_pr.number = 123
        mock_pr.html_url = "https://github.com/owner/repo/pull/123"
        mock_pr.default_branch = "main"
        mock_repo.create_pull.return_value = mock_pr
        result = create_pr(mock_repo, "owner/repo", "test-branch", [])
        self.assertEqual(result, 123)

    def test_create_pr_github_exception(self):
        """Assert create_pr returns None when GitHub API raises exception"""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.create_pull.side_effect = GithubException(404, {"data": "Not Found"})
        result = create_pr(mock_repo, "owner/repo", "test-branch", [])
        self.assertIsNone(result)


class TestUpdatePreCommit(unittest.TestCase):
    """Test update_pre_commit_config function for updating pre-commit config YAML"""

    file_src = "tests/files/pre-commit-config.yaml"
    file_dst = "tests/files/pre-commit-config-temp.yaml"
    variance_list = [
        {"owner_repo": "pycqa/flake8", "current_rev": "7.1.2", "new_rev": "7.2.0"},
        {"owner_repo": "pre-commit/pre-commit-hooks", "current_rev": "v4.0.0", "new_rev": "v5.0.0"},
    ]

    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output
        sys.stderr = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def test_update_pre_commit_return_gen(self):
        """Assert update_pre_commit_config returns a generator after updating the config file"""
        shutil.copyfile(self.file_src, self.file_dst)
        update_pre_commit_config(self.file_dst, self.variance_list)
        fn_return_generator = get_owner_repo_revs(self.file_dst)
        self.assertIsInstance(fn_return_generator, type((x for x in [])))
        os.remove(self.file_dst)


class TestZMain(unittest.TestCase):
    """Integration tests for main CLI command"""

    file = "tests/files/pre-commit-config.yaml"
    invalid_yaml = "tests/files/invalid-yaml.yaml"

    def setUp(self):
        self.runner = CliRunner()

    def test_main_help(self):
        """Assert CLI help displays correctly with zero exit code"""
        result = self.runner.invoke(main, ["--help"])
        self.assertEqual(result.exit_code, 0)

    @patch("update_pre_commit.cli.get_origin_owner_repo", return_value="owner/repo")
    @patch("update_pre_commit.cli.get_active_branch_name", return_value="main")
    @patch("update_pre_commit.cli.get_auth")
    @patch("update_pre_commit.cli.get_owner_repo_revs")
    @patch("update_pre_commit.cli.start_thread")
    def test_main_dry_run_true_failure(
        self, mock_start_thread, mock_get_revs, mock_get_auth, mock_get_branch, mock_get_repo
    ):
        """Assert CLI handles dry-run mode correctly with valid file"""
        mock_get_revs.return_value = iter([])  # Return empty generator
        mock_gh = Mock()
        mock_repo = Mock()
        mock_gh.get_repo.return_value = mock_repo
        mock_get_auth.return_value = mock_gh
        result = self.runner.invoke(main, ["--file", self.file])
        self.assertEqual(result.exit_code, 0)

    def test_main_dry_run_true_invalid_yaml(self):
        """Assert CLI returns non-zero exit code for invalid YAML file"""
        result = self.runner.invoke(main, ["--file", self.invalid_yaml])
        self.assertNotEqual(result.exit_code, 0)

    @patch("update_pre_commit.cli.get_origin_owner_repo", return_value="owner/repo")
    @patch("update_pre_commit.cli.get_active_branch_name", return_value="main")
    @patch("update_pre_commit.cli.get_auth")
    @patch("update_pre_commit.cli.get_owner_repo_revs")
    @patch("update_pre_commit.cli.start_thread")
    def test_main_dry_run_true_success(
        self, mock_start_thread, mock_get_revs, mock_get_auth, mock_get_branch, mock_get_repo
    ):
        """Assert CLI returns zero exit code in dry-run mode with empty repo list"""
        mock_get_revs.return_value = iter([])  # Return empty generator
        mock_gh = Mock()
        mock_repo = Mock()
        mock_gh.get_repo.return_value = mock_repo
        mock_get_auth.return_value = mock_gh
        result = self.runner.invoke(main, ["--dry-run", "True"])
        self.assertEqual(result.exit_code, 0)

    @patch("update_pre_commit.cli.get_origin_owner_repo", return_value="owner/repo")
    @patch("update_pre_commit.cli.get_active_branch_name", return_value="main")
    @patch("update_pre_commit.cli.get_auth")
    @patch("update_pre_commit.cli.get_owner_repo_revs")
    @patch("update_pre_commit.cli.update_pre_commit_config")
    @patch("update_pre_commit.cli.checkout_new_branch", return_value="new-branch")
    @patch("update_pre_commit.cli.push_commit")
    @patch("update_pre_commit.cli.create_pr", return_value=123)
    @patch("update_pre_commit.cli.Github")
    @patch("update_pre_commit.cli.git")
    def test_main_create_pr_success(
        self,
        mock_git,
        mock_github,
        mock_create_pr,
        mock_push,
        mock_checkout,
        mock_update,
        mock_get_revs,
        mock_get_auth,
        mock_get_branch,
        mock_get_repo,
    ):
        """Assert CLI creates PR when open_pr=True and variance is detected"""

        mock_get_revs.return_value = iter(
            [
                {"owner_repo": "adrienverge/yamllint", "current_rev": "v1.37.0"},
            ]
        )

        mock_gh = Mock()
        mock_repo = Mock()
        mock_release = Mock()
        mock_release.tag_name = "v1.38.0"
        mock_repo.get_latest_release.return_value = mock_release
        mock_gh.get_repo.return_value = mock_repo
        mock_github.return_value = mock_gh
        mock_get_auth.return_value = mock_gh

        # Setup mock git repo with heads for checkout
        mock_repo_instance = Mock()
        mock_active_branch = Mock()
        mock_active_branch.name = "main"
        mock_active_branch.checkout = Mock()  # Mock checkout to prevent git errors
        mock_repo_instance.active_branch = mock_active_branch
        mock_repo_instance.heads = {"main": mock_active_branch}
        mock_git.Repo.return_value = mock_repo_instance

        result = self.runner.invoke(main, ["--file", self.file, "--dry-run", "False", "--open-pr", "True"])
        self.assertEqual(result.exit_code, 0)

    @patch("update_pre_commit.cli.get_origin_owner_repo", return_value="owner/repo")
    @patch("update_pre_commit.cli.get_active_branch_name", return_value="main")
    @patch("update_pre_commit.cli.get_auth")
    @patch("update_pre_commit.cli.get_owner_repo_revs")
    @patch("update_pre_commit.cli.update_pre_commit_config")
    @patch("update_pre_commit.cli.checkout_new_branch")
    @patch("update_pre_commit.cli.push_commit")
    @patch("update_pre_commit.cli.create_pr")
    @patch("update_pre_commit.cli.Github")
    def test_main_update_no_pr(
        self,
        mock_github,
        mock_create_pr,
        mock_push,
        mock_checkout,
        mock_update,
        mock_get_revs,
        mock_get_auth,
        mock_get_branch,
        mock_get_repo,
    ):
        """Assert CLI updates config without PR when open_pr=False"""
        mock_get_revs.return_value = iter(
            [
                {"owner_repo": "adrienverge/yamllint", "current_rev": "v1.37.0"},
            ]
        )

        mock_gh = Mock()
        mock_repo = Mock()
        mock_release = Mock()
        mock_release.tag_name = "v1.38.0"
        mock_repo.get_latest_release.return_value = mock_release
        mock_gh.get_repo.return_value = mock_repo
        mock_github.return_value = mock_gh
        mock_get_auth.return_value = mock_gh

        result = self.runner.invoke(main, ["--file", self.file, "--dry-run", "False", "--open-pr", "False"])
        self.assertEqual(result.exit_code, 0)

    def test_main_dry_run_typo_failure(self):
        """Assert CLI returns non-zero exit code for invalid dry-run value"""
        result = self.runner.invoke(main, ["--dry-run", "Typo"])
        self.assertNotEqual(result.exit_code, 0)

    def test_main_file_not_exist_failure(self):
        """Assert CLI returns non-zero exit code for non-existent file"""
        result = self.runner.invoke(main, ["--file", "file-not-exist.yaml"])
        self.assertNotEqual(result.exit_code, 0)

    def test_main_invalid_option_failure(self):
        """Assert CLI returns non-zero exit code for invalid options"""
        result = self.runner.invoke(main, ["--hello", "world"])
        self.assertNotEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
