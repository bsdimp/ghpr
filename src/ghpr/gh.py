"""`gh` command subroutines/interfaces."""

import json
import os
import subprocess
import typing

if typing.TYPE_CHECKING:
    from typing import Self

import click

# ruff: noqa: S603

_DRY_RUN_VIEW_RESULTS = {"labels": [], "assignees": [], "reviews": []}


class GHHelper:
    """Helper class for GitHub CLI operations."""

    def __init__(
        self: "Self",
        freebsd_src_repo: str,
        dry_run: bool = False,
        verbose: bool = False,
        working_dir: str | os.PathLike | None = None,
    ) -> None:
        self.freebsd_src_repo = freebsd_src_repo
        self.dry_run = dry_run
        self.verbose = verbose
        self.working_dir = working_dir

    def run(
        self: "Self",
        args: list[str],
        check: bool = True,
        capture: bool = False,
        **subproc_kwargs: dict[str, ...],
    ) -> subprocess.CompletedProcess:
        """Execute `gh`."""
        subproc_kwargs = subproc_kwargs or {}

        cmd = ["gh", *args]
        if self.verbose:
            click.echo(f"+ {' '.join(cmd)}")

        if self.dry_run:
            # In dry-run mode, don't execute anything
            return subprocess.CompletedProcess(cmd, stdout="", stderr="", returncode=0)

        if capture:
            subproc_kwargs["capture_output"] = True
            subproc_kwargs["text"] = True
        return subprocess.run(cmd, check=check, cwd=self.working_dir, **subproc_kwargs)

    def gh_pr(
        self: "Self",
        command: str,
        pr: int,
        args: list[str],
    ) -> subprocess.CompletedProcess | None:
        """Run `gh pr`.

        This method runs `gh pr` with an appropriate `--repo` argument, combined with
        the provided `args`.

        Args:
            command: commands passed verbatim to `gh pr`, e.g., "view", "close", etc.
            pr: GitHub PR #, e.g., 2048.
            args: arguments to pass directly to `gh pr`.

        Returns:
            A `subprocess.CompletedProcess` object representing the result of the
            `gh pr` command, or `None` if `--dry-run` was specified previously.

        """
        cmd = [
            "pr",
            "--repo",
            self.freebsd_src_repo,
            command,
            str(pr),
            *args,
        ]
        return self.run(cmd, check=True, text=True)

    def pr_checkout(
        self: "Self",
        pr_number: int,
        branch: str,
    ) -> None:
        """Checkout a PR into a branch."""
        self.gh_pr("checkout", pr_number, ["-b", branch])

    def pr_edit(
        self: "Self",
        pr_number: int,
        add_label: str | None = None,
        remove_label: str | None = None,
    ) -> None:
        """Edit PR metadata."""
        args = []
        if add_label:
            args.extend(["--add-label", add_label])
        if remove_label:
            args.extend(["--remove-label", remove_label])
        self.gh_pr("edit", pr_number, args)

    def pr_close(self: "Self", pr_number: int, comment: str | None = None) -> None:
        """Close a PR."""
        args = ["--comment", comment] if comment else []
        self.gh_pr("close", pr_number, args)

    def pr_view(self: "Self", pr_number: int) -> dict:
        """Get PR information including labels, assignees, and reviews."""
        if self.dry_run:
            return _DRY_RUN_VIEW_RESULTS
        args = [
            "--json",
            "labels,assignees,reviews",
        ]
        result = self.gh_pr("view", pr_number, args)
        return json.loads(result.stdout)
