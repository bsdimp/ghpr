"""'ghpr.cli' module tests.

TODO: further mock out interfaces/test CLI paths more thoroughly.
"""

from unittest import mock

import pytest
from click.testing import CliRunner

from ghpr import __main__

from . import format_result, sandbox, setup_freebsd_remote


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
    def test_without_freebsd_remote(bare_repo: ...) -> None:
        """Confirm that pointing ghpr at a repo without a freebsd remote fails."""
        runner = CliRunner()
        with runner.isolated_filesystem(bare_repo):
            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code != 0, format_result(result)

    @staticmethod
    @pytest.mark.parametrize(
        "push_remote",
        [
            "https://bogus/src",
            "git@bogus:src",
            "git+ssh://bogus/src",
        ],
    )
    def test_bogus_remotes(bare_repo: ..., push_remote: str) -> None:
        """Confirm that pointing ghpr at a repo with bogus freebsd remotes fails.

        This is not an exhaustive battery of tests.
        """
        setup_freebsd_remote(bare_repo, push_remote)
        runner = CliRunner()
        with runner.isolated_filesystem(bare_repo):
            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code != 0, format_result(result)

    @staticmethod
    @pytest.mark.parametrize(
        "fetch_remote",
        [
            __main__.ALLOWED_STAGING_FETCH_REMOTES[-1].upper(),
            *__main__.ALLOWED_STAGING_FETCH_REMOTES,
        ],
    )
    def test_allowed_fetch_remotes(
        bare_repo: ...,
        allowed_staging_url: str,
        fetch_remote: str | None,
    ) -> None:
        """Confirm that pointing ghpr at a repo with valid freebsd remotes works.

        This is not an exhaustive battery of tests.
        """
        setup_freebsd_remote(bare_repo, fetch_remote, allowed_staging_url)
        runner = CliRunner()
        with runner.isolated_filesystem(bare_repo):
            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code == 0, format_result(result)

    @staticmethod
    def test_push_remote_defaults_to_fetch_remote(
        bare_repo: ...,
        allowed_staging_url: str,
    ) -> None:
        """Confirm that pointing ghpr at a repo with just a fetch remote works."""
        setup_freebsd_remote(bare_repo, allowed_staging_url, None)
        runner = CliRunner()
        with runner.isolated_filesystem(bare_repo):
            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code == 0, format_result(result)

    @staticmethod
    @pytest.mark.parametrize(
        "push_remote",
        [
            None,
            __main__.ALLOWED_STAGING_PUSH_REMOTES[-1].upper(),
            *__main__.ALLOWED_STAGING_PUSH_REMOTES,
        ],
    )
    def test_allowed_push_remotes(
        bare_repo: ...,
        allowed_staging_url: str,
        push_remote: str,
    ) -> None:
        """Confirm that pointing ghpr at a repo with valid freebsd push remote works.

        This is not an exhaustive battery of tests.
        """
        setup_freebsd_remote(bare_repo, allowed_staging_url, push_remote)
        runner = CliRunner()
        with runner.isolated_filesystem(bare_repo):
            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code == 0, format_result(result)

    @staticmethod
    def test_dry_run(setup_staging: ...) -> None:
        """Confirm that `--dry-run` works."""
        runner = CliRunner()
        staging_repo = setup_staging
        with runner.isolated_filesystem(staging_repo):
            result = runner.invoke(__main__.cli, ["--dry-run", "init"])
            assert result.exit_code == 0, format_result(result)

    @staticmethod
    @pytest.mark.xfail(reason="--work-dir doesn't work fully yet.")
    def test_work_dir_option(setup_staging: ...) -> None:
        """Confirm that `--work-dir` works."""
        runner = CliRunner()
        staging_repo = setup_staging
        with runner.isolated_filesystem():
            result = runner.invoke(
                __main__.cli,
                ["--work-dir", str(staging_repo.resolve()), "init"],
            )
            assert result.exit_code == 0, format_result(result)

    @staticmethod
    def test_force(default_freebsd_remote: ...) -> None:
        """Confirm that `--force` is effectively a no-op if run on fresh repo."""
        runner = CliRunner()
        with runner.isolated_filesystem(default_freebsd_remote):
            result = runner.invoke(__main__.cli, ["init", "--force"])
            assert result.exit_code == 0, format_result(result)
            assert "has already been initialized" not in result.output

    @staticmethod
    def test_init_already_inited_succeeds(default_freebsd_remote: ...) -> None:
        """Confirm behavior when  `--force` works."""
        runner = CliRunner()
        with runner.isolated_filesystem(default_freebsd_remote):
            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code == 0, format_result(result)

            result = runner.invoke(__main__.cli, ["init"])
            assert result.exit_code == 0, format_result(result)
            assert "has already been initialized" in result.output

            result = runner.invoke(__main__.cli, ["init", "--force"])
            assert result.exit_code == 0, format_result(result)
            assert "Cleaning up existing " in result.output
            assert "Cleanup complete" in result.output

    @staticmethod
    def test_verbose(default_freebsd_remote: ...) -> None:
        """Confirm that `--verbose` works."""
        runner = CliRunner()
        with runner.isolated_filesystem(default_freebsd_remote):
            result = runner.invoke(__main__.cli, ["--verbose", "init"])
            assert result.exit_code == 0, format_result(result)
            assert result.output_bytes, format_result(result)


class TestPush:
    """`ghpr push` tests."""

    @staticmethod
    def test_no_init_fails() -> None:
        """Confirm that running the command without running `ghpr init` first fails."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(__main__.cli, ["push"])
            assert result.exit_code != 0, format_result(result)

    @staticmethod
    def test_dry_run(setup_staging: ...) -> None:
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
    def test_dry_run(setup_staging: ...) -> None:
        """Confirm that `--dry-run` works."""
        staging_repo = setup_staging
        runner = CliRunner()
        with runner.isolated_filesystem(staging_repo):
            dummy_pr = "0"
            result = runner.invoke(__main__.cli, ["--dry-run", "stage", dummy_pr])
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
    def test_dry_run(setup_staging: ...) -> None:
        """Confirm that `--dry-run` works."""
        staging_repo = setup_staging
        runner = CliRunner()
        with runner.isolated_filesystem(staging_repo):
            result = runner.invoke(__main__.cli, ["--dry-run", "status"])
            assert result.exit_code == 0, format_result(result)


class TestUnstage:
    """`ghpr unstage` tests."""

    @staticmethod
    def test_no_init_fails() -> None:
        """Confirm that running the command without running `ghpr init` first fails."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(__main__.cli, ["unstage", "0"])
            assert result.exit_code != 0, format_result(result)

    @staticmethod
    def test_dry_run(setup_staging: ...) -> None:
        """Confirm that `--dry-run` works."""
        staging_repo = setup_staging
        runner = CliRunner()
        with runner.isolated_filesystem(staging_repo):
            result = runner.invoke(__main__.cli, ["--dry-run", "unstage", "0"])
            assert result.exit_code == 0, format_result(result)


class TestGHPRInit:
    """`GHPR.init` tests which go beyond what `TestInit` can easily test."""

    @staticmethod
    def test_init_branch_exists_but_not_initialized(
        default_freebsd_remote: ...,
    ) -> None:
        """Confirm that repos with existing staging branches are rebased-not deleted."""
        with sandbox(default_freebsd_remote):
            ghpr = __main__.GHPR()
            with mock.patch.object(ghpr, "is_initialized", return_value=False):
                with mock.patch.multiple(
                    ghpr.githelper,
                    branch_exists=mock.DEFAULT,
                    rebase=mock.DEFAULT,
                ) as gh_mocks:
                    gh_mocks["branch_exists"].return_value = True
                    ghpr.init()
                    gh_mocks["rebase"].assert_called_with(__main__.DEFAULT_BASE)
