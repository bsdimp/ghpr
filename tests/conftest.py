"""Common decorator logic, etc.

Copyright (c) 2026 Enji Cooper <ngie@FreeBSD.org>

SPDX-License-Identifier: BSD-2-Clause
"""

import pathlib
import shutil
from collections.abc import Generator

import git
import pytest
from click.testing import CliRunner
from git import Repo

from ghpr import __main__

from . import format_result, setup_freebsd_remote


@pytest.fixture
def bare_repo(tmp_path: ...) -> Generator[pathlib.Path]:
    """Fixture that sets up a bare git repo."""
    git_repo_dir = tmp_path / "git"
    git.Repo.init(git_repo_dir, mkdir=True)
    repo = git.Repo(git_repo_dir)
    (git_repo_dir / "README.md").touch()
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")
    repo.create_head("main")
    yield git_repo_dir
    shutil.rmtree(git_repo_dir)


@pytest.fixture(scope="session")
def allowed_staging_url() -> str:
    """Shorthand for the last element in `ALLOWED_STAGING_PUSH_REMOTES`.

    The last element is guaranteed to work for both fetch and push.
    """
    return __main__.ALLOWED_STAGING_PUSH_REMOTES[-1]


@pytest.fixture
def default_freebsd_remote(
    bare_repo: ...,
    allowed_staging_url: str,
) -> Repo:
    """Set up a default `freebsd` remote for testing."""
    setup_freebsd_remote(bare_repo, allowed_staging_url)
    return bare_repo


@pytest.fixture
def setup_staging(default_freebsd_remote: ...) -> Repo:
    """Procedure which sets up a staging branch for testing."""
    runner = CliRunner()
    with runner.isolated_filesystem(default_freebsd_remote):
        result = runner.invoke(__main__.cli, ["init"])
        assert result.exit_code == 0, format_result(result)
    return default_freebsd_remote
