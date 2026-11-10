"""'ghpr.git' module tests.

TODO: improve these tests by further mocking out the inputs/outputs of `GitHelper`.

Copyright (c) 2026 Enji Cooper <ngie@FreeBSD.org>

SPDX-License-Identifier: BSD-2-Clause
"""

from collections.abc import Generator
from unittest.mock import patch

import git
import pytest

from ghpr.git import GitConfig, GitHelper

from . import sandbox


class TestGitHelper:
    """GitHelper test suite."""

    @staticmethod
    def test_branch_exists(setup_staging: Generator[git.Repo]) -> None:
        """`GitHelper.branch_exists` tests."""
        staging_repo = setup_staging
        with sandbox(staging_repo):
            gh = GitHelper(verbose=True)
            assert gh.branch_exists("main")
            assert not gh.branch_exists("doesnotexist")


class TestGitConfig:
    """GitConfig test suite."""

    @staticmethod
    @pytest.mark.parametrize(
        "value,config_type",
        [
            pytest.param("bar", None, id="No type"),
            pytest.param(0, "bool-or-int", id="boolean"),
            pytest.param(4, "bool-or-int", id="integer"),
            pytest.param(__file__, "path", id="path"),
        ],
    )
    def test_basic_set_unset_flow(
        setup_staging: Generator[git.Repo],
        value: ...,
        config_type: str | None,
    ) -> None:
        """Test the basic set/unset workflow for `GitConfig`.

        - Set a variable with add=True.
        - Query the value.
        - Unset the value.
        - Query the value again.
        """
        staging_repo = setup_staging
        with sandbox(staging_repo):
            gc = GitConfig(verbose=True)
            # gc.add_section(section)
            key = "test.key"
            gc.set(key, value, add=True, config_type=config_type)
            assert gc.get(key) == str(value)
            gc.unset(key)
            assert not gc.get(key)

    @staticmethod
    def test_get_default() -> None:
        """Test `GitConfig.get(..., default=...)`.

        Confirm that `GitConfig.get(..., default=...)` returns the value passed to
        `default` when the `.get(..)` call fails.
        """
        gc = GitConfig(verbose=True)
        with patch.object(gc, "config") as mock_method:
            mock_method.side_effect = git.exc.GitCommandError("bogus")
            default_value = "bogus"
            key = "test.key"
            assert default_value == gc.get(key, default=default_value)

    @staticmethod
    @pytest.mark.parametrize(
        "mock_input,expected_output",
        [
            pytest.param(
                "single line",
                ["single line"],
                id="a single line returns a single element",
            ),
            pytest.param(
                "multiple\nlines",
                ["multiple", "lines"],
                id="multiple lines return multiple elements",
            ),
        ],
    )
    def test_get_all(mock_input: str, expected_output: list[str]) -> None:
        """Test `GitConfig.get_all()`'s happy path logic."""
        gc = GitConfig(verbose=True)
        with patch.object(gc, "config", return_value=mock_input):
            assert gc.get_all("bogus") == expected_output
