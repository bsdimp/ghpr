"""'ghpr.gh' module tests.

TODO: improve these tests by further mocking out the inputs/outputs of `GHHelper`.
"""

import json
import subprocess
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch

import pytest

from ghpr import gh


class TestGHHelperPRCommands:
    """GHHelper PR-related command test suite."""

    @staticmethod
    def test_checkout(setup_staging: ...) -> None:
        """Test `gh pr checkout` integration."""
        staging_repo = setup_staging
        ghh = gh.GHHelper(staging_repo, verbose=True)
        with patch.object(ghh, "run") as mock_run:
            ghh.pr_checkout(0, "bogus")
            mock_run.assert_called()

    @staticmethod
    def test_close(setup_staging: ...) -> None:
        """Test `gh pr close` integration."""
        staging_repo = setup_staging
        ghh = gh.GHHelper(staging_repo, verbose=True)
        with patch.object(ghh, "run") as mock_run:
            ghh.pr_close(0)
            mock_run.assert_called()

    @staticmethod
    def test_edit(setup_staging: ...) -> None:
        """Test `gh pr edit` integration."""
        staging_repo = setup_staging
        ghh = gh.GHHelper(staging_repo, verbose=True)
        with patch.object(ghh, "run") as mock_run:
            ghh.pr_edit(0, add_label="campbell_soup")
            mock_run.assert_called()

    @staticmethod
    def test_view_dry_run(setup_staging: ...) -> None:
        """Test `gh pr view` (dry-run) integration."""
        staging_repo = setup_staging
        ghh = gh.GHHelper(staging_repo, dry_run=True, verbose=True)
        with patch.object(ghh, "gh_pr") as mock_gh_pr:
            assert ghh.pr_view(0) == gh._DRY_RUN_VIEW_RESULTS
            mock_gh_pr.assert_not_called()

    @staticmethod
    def test_view_mocked(setup_staging: ...) -> None:
        """Test `gh pr view` (mocked) integration."""
        staging_repo = setup_staging
        ghh = gh.GHHelper(staging_repo, verbose=True)
        with patch.object(ghh, "run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                [],
                returncode=0,
                stdout=json.dumps({"bogus": "json"}),
                stderr="",
            )
            ghh.pr_view(0)
            mock_run.assert_called()

    @staticmethod
    def test_assert_logged_in_passes(setup_staging: ...) -> None:
        """Test positive behavior for GHHelper.assert_logged_in(..)."""

        def always_pass(*args, **kwargs):
            """Always pass :)."""

        staging_repo = setup_staging
        ghh = gh.GHHelper(staging_repo, verbose=True)
        with patch.object(ghh, "run", side_effect=always_pass):
            ghh.assert_logged_in()

    @staticmethod
    def test_assert_logged_in_failure_caught(setup_staging: ...) -> None:
        """Test negative behavior for GHHelper.assert_logged_in(..) - scenario 1.

        Scenario 1: the expected exception (`subprocess.CalledProcessError`) is raised
        on failure and converted into a RuntimeError.
        """
        staging_repo = setup_staging
        run_side_effect = subprocess.CalledProcessError(-1, ["bogus"])
        ghh = gh.GHHelper(staging_repo, verbose=True)
        with patch.object(ghh, "run", side_effect=run_side_effect):
            with pytest.raises(RuntimeError):
                ghh.assert_logged_in()

    @staticmethod
    def test_assert_logged_in_failure_not_caught(setup_staging: ...) -> None:
        """Test negative behavior for GHHelper.assert_logged_in(..) - scenario 2.

        Scenario 2: an unexpected exception is raised from the inner function, and
        subsequently bubbled up as-is.
        """
        staging_repo = setup_staging
        run_side_effect = AssertionError("test failure on purpose")
        ghh = gh.GHHelper(staging_repo, verbose=True)
        with patch.object(ghh, "run", side_effect=run_side_effect):
            with pytest.raises(run_side_effect.__class__):
                ghh.assert_logged_in()
