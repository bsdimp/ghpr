"""End-to-end tests for `ghpr`."""

# Stuff that doesn't need to be fixed:

# ruff: noqa: S101

# Stuff that's worth fixing, but is being suppressed for now.

# ruff: noqa: ANN001, ANN201, FIX002, TD002, TD003

import os
import pathlib
import shutil
from contextlib import contextmanager

import git
import pytest
from click.testing import CliRunner

from ghpr import __main__


@pytest.fixture
def bare_repo(tmp_path):
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
def allowed_staging_url():
    """Shorthand for the first element in `ALLOWED_STAGING_URLS`."""
    yield __main__.ALLOWED_STAGING_URLS[0]


def format_result(result) -> str:
    """Format results from `click.invoke(..)`."""
    return f"{result=} {result.output=}"


def setup_freebsd_remote(repo_dir: pathlib.Path, remote: str) -> None:
    """Fixture that sets up a bogus repo with the https://."""
    repo = git.Repo(repo_dir)
    repo.create_remote("freebsd", remote)


@pytest.fixture
def default_freebsd_remote(bare_repo, allowed_staging_url):
    """Set up a default `freebsd` remote for testing."""
    setup_freebsd_remote(bare_repo, allowed_staging_url)
    yield bare_repo


@pytest.fixture
def setup_staging(default_freebsd_remote):
    runner = CliRunner()
    with runner.isolated_filesystem(default_freebsd_remote):
        result = runner.invoke(__main__.cli, ["init"])
        assert result.exit_code == 0, format_result(result)
    yield default_freebsd_remote


class TestInit:
    """`ghpr init` tests."""

    @staticmethod
    def test_from_non_git_repo() -> None:
        """Confirm that pointing ghpr at a repo without a freebsd remote fails."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code != 0, format_result(result)

    @staticmethod
    def test_without_freebsd_remote(bare_repo) -> None:
        """Confirm that pointing ghpr at a repo without a freebsd remote fails."""
        runner = CliRunner()
        with runner.isolated_filesystem(bare_repo):
            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code != 0, format_result(result)

    @staticmethod
    @pytest.mark.parametrize(
        "remote",
        [
            "https://bogus/src",
            "git@bogus:src",
            "git+ssh://bogus/src",
        ],
    )
    def test_bogus_remotes(bare_repo, remote) -> None:
        """Confirm that pointing ghpr at a repo with a bogus freebsd remote fails.

        This is not an exhaustive battery of tests.
        """
        setup_freebsd_remote(bare_repo, remote)
        runner = CliRunner()
        with runner.isolated_filesystem(bare_repo):
            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code != 0, format_result(result)

    @staticmethod
    @pytest.mark.parametrize(
        "remote",
        __main__.ALLOWED_STAGING_URLS,
    )
    def test_allowed_remotes(bare_repo, remote) -> None:
        """Confirm that pointing ghpr at a repo with a bogus.

        This is not an exhaustive battery of tests.
        """
        setup_freebsd_remote(bare_repo, remote)
        runner = CliRunner()
        with runner.isolated_filesystem(bare_repo):
            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code == 0, format_result(result)

    @staticmethod
    def test_dry_run(default_freebsd_remote) -> None:
        """Confirm that `--dry-run` works."""
        runner = CliRunner()
        with runner.isolated_filesystem(default_freebsd_remote):
            result = runner.invoke(__main__.cli, ["--dry-run", "init"])
            assert result.exit_code == 0, format_result(result)

    @staticmethod
    def test_force(default_freebsd_remote) -> None:
        """Confirm that `--force` works."""
        runner = CliRunner()
        with runner.isolated_filesystem(default_freebsd_remote):
            result = runner.invoke(__main__.cli, ["init", "--force"])
            assert result.exit_code == 0, format_result(result)

    @staticmethod
    def test_init_already_inited_succeeds(default_freebsd_remote) -> None:
        """Confirm that `--force` works."""
        runner = CliRunner()
        with runner.isolated_filesystem(default_freebsd_remote):
            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code == 0, format_result(result)

            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code == 0, format_result(result)

    @staticmethod
    def test_verbose(default_freebsd_remote) -> None:
        """Confirm that `--verbose` works."""
        runner = CliRunner()
        with runner.isolated_filesystem(default_freebsd_remote):
            result = runner.invoke(__main__.cli, ["--verbose", "init"])
            assert result.exit_code == 0, format_result(result)
            assert result.output_bytes, format_result(result)


class TestPush:
    """`ghpr push` tests."""

    @staticmethod
    @pytest.mark.xfail
    def test_no_init_fails() -> None:
        """Confirm that running the command without running `ghpr init` first fails."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(__main__.cli, ["push"])
            assert result.exit_code != 0, format_result(result)

    @staticmethod
    @pytest.mark.xfail
    def test_dry_run(setup_staging) -> None:
        """Confirm that `--dry-run` works."""
        staging_repo = setup_staging
        runner = CliRunner()
        with runner.isolated_filesystem(staging_repo):
            result = runner.invoke(__main__.cli, ["--dry-run", "push"])
            assert result.exit_code == 0, format_result(result)


class TestStage:
    """`ghpr stage` tests."""

    @staticmethod
    def test_no_init_fails() -> None:
        """Confirm that running the command without running `ghpr init` first fails."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(__main__.cli, ["stage", "0"])
            assert result.exit_code != 0, format_result(result)

    @staticmethod
    def test_dry_run(setup_staging) -> None:
        """Confirm that `--dry-run` works."""
        staging_repo = setup_staging
        runner = CliRunner()
        with runner.isolated_filesystem(staging_repo):
            result = runner.invoke(__main__.cli, ["--dry-run", "stage", "0"])
            assert result.exit_code == 0, format_result(result)


class TestStatus:
    """`ghpr status` tests."""

    @staticmethod
    def test_no_init_fails() -> None:
        """Confirm that running the command without running `ghpr init` first fails."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(__main__.cli, ["status"])
            assert result.exit_code != 0, format_result(result)

    @staticmethod
    @pytest.mark.xfail
    def test_dry_run(setup_staging) -> None:
        """Confirm that `--dry-run` works."""
        staging_repo = setup_staging
        runner = CliRunner()
        with runner.isolated_filesystem(staging_repo):
            result = runner.invoke(__main__.cli, ["--dry-run", "status"])
            assert result.exit_code == 0, format_result(result)


class TestUnstage:
    """`ghpr unstage` tests."""

    @staticmethod
    @pytest.mark.xfail
    def test_no_init_fails() -> None:
        """Confirm that running the command without running `ghpr init` first fails."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(__main__.cli, ["unstage", "0"])
            assert result.exit_code != 0, format_result(result)

    @staticmethod
    @pytest.mark.xfail
    def test_dry_run(setup_staging) -> None:
        """Confirm that `--dry-run` works."""
        staging_repo = setup_staging
        runner = CliRunner()
        with runner.isolated_filesystem(staging_repo):
            result = runner.invoke(__main__.cli, ["--dry-run", "unstage", "0"])
            assert result.exit_code == 0, format_result(result)


@contextmanager
def chdir(new_path: pathlib.Path) -> None:
    old_path = os.getcwd()
    os.chdir(new_path)
    try:
        yield
    finally:
        os.chdir(old_path)


class TestGitHelper:
    @staticmethod
    def test_dry_run(setup_staging) -> None:
        """Confirm that `--dry-run` works."""
        staging_repo = setup_staging
        with chdir(staging_repo):
            assert __main__.GitHelper.branch_exists("main")
            assert not __main__.GitHelper.branch_exists("doesnotexist")
