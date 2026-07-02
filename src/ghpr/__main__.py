"""ghpr - GitHub Pull Request landing tool for FreeBSD.

Unified tool to land GitHub pull requests into FreeBSD repositories.
Combines the functionality of ghpr-init.sh, ghpr-stage.sh, and ghpr-push.sh.

Copyright (c) 2026 Warner Losh <imp@FreeBSD.org>
Copyright (c) 2026 Enji Cooper <ngie@FreeBSD.org>

SPDX-License-Identifier: BSD-2-Clause
"""

# These issues are [generally] annoying noise from `ruff`.
#
# ruff: noqa: S603

from __future__ import annotations

import contextlib
import getpass
import subprocess
import sys
import traceback
import typing
from pathlib import Path

import click
import git

from . import __version__, logging
from .gh import GHHelper
from .git import GitConfig, GitHelper

if typing.TYPE_CHECKING:
    from typing import Self

ALLOWED_STAGING_URLS = [
    "git@gitrepo.freebsd.org:src.git",
    "ssh://git@gitrepo.freebsd.org/src.git",
]
DEFAULT_BASE = "main"
DEFAULT_FREEBSD_SRC_GITHUB_REPO = "freebsd/freebsd-src"
DEFAULT_STAGING_BRANCH = "staging"
DEFAULT_STAGING_REMOTE = "freebsd"
LOGGER = logging.get_logger("ghpr")
MERGED_LABEL = "merged"
STAGED_LABEL = "staged"


class GHPR:
    """Main class for GitHub PR landing operations."""

    def __init__(
        self: "Self",
        dry_run: bool = False,
        base: str = DEFAULT_BASE,
        freebsd_src_repo: str = DEFAULT_FREEBSD_SRC_GITHUB_REPO,
        staging_branch: str = DEFAULT_STAGING_BRANCH,
        staging_remote: str = DEFAULT_STAGING_REMOTE,
        verbose: bool = False,
        work_dir: str | None = None,
    ) -> None:
        self.githelper = GitHelper(
            dry_run=dry_run,
            verbose=verbose,
            working_dir=work_dir,
        )
        self.gitconfig = GitConfig(dry_run=dry_run, verbose=verbose)
        self.ghhelper = GHHelper(
            dry_run=dry_run,
            freebsd_src_repo=freebsd_src_repo,
            verbose=verbose,
            working_dir=work_dir,
        )

        self.base = base
        self.dry_run = dry_run
        self.config_prefix = f"branch.{staging_branch}.opabinia"
        self.freebsd_src_repo = freebsd_src_repo
        self.staging_branch = staging_branch
        self.staging_remote = staging_remote
        self.verbose = verbose

        if dry_run:
            click.echo("DRY RUN MODE - No changes will be made\n")

    @staticmethod
    def die(message: str) -> None:
        """Print error and exit."""
        sys.exit(f"Error: {message}")

    def is_initialized(self) -> bool:
        """Check if staging branch is initialized."""
        return self.gitconfig.get(self.config_prefix) == "true"

    def get_base(self) -> str:
        """Get the base branch for staging."""
        base = self.gitconfig.get(f"{self.config_prefix}.base")
        if not base:
            self.die(f"No base set on {self.staging_branch}")
        return base

    def get_prs(self) -> list[str]:
        """Get list of PRs in staging branch."""
        return self.gitconfig.get_all(f"{self.config_prefix}.prs")

    def _check_staging_remote(self) -> None:
        """Verify the staging remote.

        Confirm that the staging branch remote:
        - .. exists.
        - .. points to one of the expected URLs.
        """
        # Check if remote exists
        try:
            fetch_url = self.githelper.remote(
                ["get-url", self.staging_remote],
                strip_newline_in_stdout=True,
                with_extended_output=False,
                safe=True,
            )
        except git.exc.GitCommandError:
            self.die(
                f"No {self.staging_remote!r} remote found.\n"
                f"Please add it with:\n"
                f"  git remote add {self.staging_remote} {ALLOWED_STAGING_URLS[0]}",
            )

        def validate_url(url: str, desc: str, set_url_flags: str) -> None:
            """Confirm that the URL specified is valid."""
            if url.lower() not in ALLOWED_STAGING_URLS:
                set_url_args = (
                    f"{set_url_flags}{self.staging_remote} {ALLOWED_STAGING_URLS[0]}"
                )
                self.die(
                    f"{self.staging_remote!r} remote's {desc} URL is incorrect.\n"
                    f"Allowed URLs: {ALLOWED_STAGING_URLS!r}\n"
                    f"Got:      {url!r}\n"
                    f"Please update it with:\n"
                    f"  git remote set-url {set_url_args}",
                )

        validate_url(fetch_url, "fetch", "")

        # Check push URL
        try:
            # If no separate push URL, it uses fetch URL
            push_url = self.githelper.remote(
                ["get-url", "--push", self.staging_remote],
                strip_newline_in_stdout=True,
                with_extended_output=False,
                safe=True,
            )
        except subprocess.CalledProcessError:
            push_url = fetch_url

        validate_url(push_url, "push", "--push")

        if self.verbose:
            click.echo(f"✓ {self.staging_remote!r} remote is correctly configured")

    def init(self: "Self", force: bool = False) -> None:
        """Initialize staging branch for PR landing (ghpr-init.sh)."""
        # Check that the staging branch's remote is properly configured
        staging_branch = self.staging_branch

        self._check_staging_remote()
        if force:
            click.echo("Force re-initialization requested")
            if self.is_initialized() or self.githelper.branch_exists(staging_branch):
                msg = f"Cleaning up existing {staging_branch} branch and config..."
                click.echo(msg)
                # Remove all config for this staging branch
                self.gitconfig.remove_section(self.config_prefix)
                # Checkout base branch if we're currently on staging
                # (can't delete a branch we're on)
                self.githelper.checkout(self.base)
                # Delete the branch if it exists
                self.githelper.delete_branch(staging_branch)
                click.echo("Cleanup complete")

        if self.is_initialized():
            click.echo(f"Branch {staging_branch} has already been initialized")
            return

        if self.githelper.branch_exists(staging_branch):
            click.echo(
                f"Branch {staging_branch} already exists. "
                f"Skipping creation, but rebasing to {self.base}",
            )
            self.githelper.rebase(self.base)
        else:
            click.echo(f"Creating {staging_branch} from {self.base} to land changes")
            try:
                self.githelper.checkout(staging_branch, create=True, base=self.base)
            except git.exc.GitCommandError:
                click.echo(traceback.format_exc())
                self.die(f"Can't create {staging_branch}")

        try:
            self.gitconfig.set(self.config_prefix, "true", config_type="bool")
            self.gitconfig.set(f"{self.config_prefix}.base", self.base)
        except git.exc.GitCommandError:
            click.echo(traceback.format_exc())
            self.die("Can't annotate branch config")

        click.echo(f"Staging branch {staging_branch} initialized successfully")

    def update_to_upstream(self: Self) -> None:
        """Update base branch and rebase staging onto it."""
        click.echo(f"Updating {self.base} and rebasing {self.staging_branch}...")
        self.githelper.checkout(self.base)
        self.githelper.pull(rebase=True)
        self.githelper.rebase(self.base, interactive=True)

    def _checkstyle(self: "Self", base: str, tip: str) -> None:
        """Run style checker if it exists.

        Args:
            base: base revision.
            tip: target or HEAD revision.

        """
        checkstyle = Path("tools/build/checkstyle9.pl")
        if not checkstyle.exists():
            return
        LOGGER.info("running style checker...")
        cmd = ["perl", str(checkstyle), f"{base}..{tip}"]
        if self.verbose or self.dry_run:
            click.echo(f"+ {' '.join(cmd)}")
        if self.dry_run:
            return
        if subprocess.call(cmd):  # Don't fail on style issues
            LOGGER.warning("style checker found issues (see output above)")

    @staticmethod
    def _pr_branch(pr_number: int) -> str:
        return f"PR-{pr_number}"

    def stage(
        self: "Self",
        pr_number: int,
        reviewer: str | None = None,
        editor: str | None = None,
        do_continue: bool = False,
        force: bool = False,
    ) -> None:
        """Stage a PR for landing (ghpr-stage.sh)."""
        if not self.is_initialized():
            self.die(
                f"Branch {self.staging_branch} has not been initialized. "
                "Run 'ghpr init' first.",
            )

        base = self.get_base()
        prs = self.get_prs()
        pr_branch = self._pr_branch(pr_number)

        # Check if PR is already staged (unless --force or --continue)
        if not do_continue and not force:
            pr_str = str(pr_number)

            # First check if PR is already in our staging branch
            if pr_str in prs:
                LOGGER.error("PR #%d is already staged", pr_number)

                # Continue on even if we can't fetch PR info..
                with contextlib.suppress(subprocess.CalledProcessError):
                    pr_info = self.ghhelper.pr_view(pr_number)
                    # Show assignees if any
                    assignees = pr_info.get("assignees", [])
                    if assignees:
                        assignee_logins = [a["login"] for a in assignees]
                        LOGGER.info("Assigned to: %r", assignee_logins)

                LOGGER.info("Use --force to stage anyway")
                sys.exit(1)

            # Check if PR has 'staged' label but isn't actually staged
            try:
                pr_info = self.ghhelper.pr_view(pr_number)
                labels = [label["name"] for label in pr_info.get("labels", [])]

                if STAGED_LABEL in labels:
                    LOGGER.warning(
                        "PR #%d has %r label but is not staged locally. "
                        "The label may be stale. Continuing with %s...",
                        STAGED_LABEL,
                        self.staging_branch,
                        pr_number,
                    )
            except subprocess.CalledProcessError:
                LOGGER.warning(
                    "Could not check PR status. Continuing with %s...",
                    self.staging_branch,
                    exc_info=True,
                )

        # Handle --continue for interrupted rebase
        if do_continue:
            LOGGER.info("Continuing interrupted rebase for PR #%d...", pr_number)

            # Check if we're in a rebase
            git_dir = Path(".git")
            rebase_merge = git_dir / "rebase-merge"
            rebase_apply = git_dir / "rebase-apply"

            if not (rebase_merge.exists() or rebase_apply.exists()):
                self.die("No rebase in progress. Cannot continue.")

            # Continue the rebase
            try:
                self.githelper.rebase(["--continue"])
            except git.exc.GitCommandError:
                self.die(
                    "Rebase continue failed. "
                    "Resolve conflicts and run 'ghpr stage --continue <PR>' again.",
                )

            # Save PR metadata if not already saved
            if str(pr_number) not in prs:
                upstream = self.gitconfig.get(f"branch.{pr_branch}.pushRemote")
                upstream_branch = self.gitconfig.get(f"branch.{pr_branch}.merge")
                if upstream_branch:
                    upstream_branch = upstream_branch.replace("refs/heads/", "")

                self.gitconfig.set(
                    f"{self.config_prefix}.prs",
                    str(pr_number),
                    add=True,
                )
                if upstream:
                    self.gitconfig.set(
                        f"{self.config_prefix}.{pr_number}.upstream",
                        upstream,
                        add=True,
                    )
                if upstream_branch:
                    self.gitconfig.set(
                        f"{self.config_prefix}.{pr_number}.upstream-branch",
                        upstream_branch,
                        add=True,
                    )

            # Move staging branch to new tip
            LOGGER.info(
                "Moving %s to include PR #%d...",
                self.staging_branch,
                pr_number,
            )
            self.githelper.move_branch(self.staging_branch)

            self._checkstyle(base, self.staging_branch)

            # Add label to GitHub PR
            LOGGER.info("Adding %r label to PR #%d...", STAGED_LABEL, pr_number)
            try:
                self.ghhelper.pr_edit(pr_number, add_label=STAGED_LABEL)
            except Exception:
                LOGGER.warning(
                    "failed to add %r label to PR #%d",
                    STAGED_LABEL,
                    pr_number,
                    exc_info=True,
                )

            # Show review information
            try:
                pr_info = self.ghhelper.pr_view(pr_number)
                reviews = pr_info.get("reviews", [])
                approvers = [
                    r["author"]["login"] for r in reviews if r["state"] == "APPROVED"
                ]
                if approvers:
                    # Remove duplicates while preserving order
                    seen = set()
                    unique_approvers = []
                    for approver in approvers:
                        if approver not in seen:
                            seen.add(approver)
                            unique_approvers.append(approver)
                    LOGGER.info("Approved by %r", unique_approvers)
            except Exception:
                LOGGER.warning("could not fetch review information", exc_info=True)

            LOGGER.info("PR #%d was staged successfully!", pr_number)
            LOGGER.info("Review the commits and when ready run 'ghpr push'!")
            return

        # Normal staging flow (not --continue)

        # Update to upstream if no PRs staged yet
        if not prs:
            self.update_to_upstream()
        else:
            self.githelper.checkout(self.staging_branch)

        # Create PR branch
        LOGGER.info("Checking out PR #%d into %s", pr_number, pr_branch)

        # Delete old PR branch if it exists
        self.githelper.delete_branch(pr_branch)

        # Checkout the PR
        try:
            self.ghhelper.pr_checkout(pr_number, pr_branch)
        except subprocess.CalledProcessError:
            self.die(f"Failed to checkout PR #{pr_number}")

        # Get upstream info
        upstream = self.gitconfig.get(f"branch.{pr_branch}.pushRemote")
        upstream_branch = self.gitconfig.get(f"branch.{pr_branch}.merge")
        if upstream_branch:
            upstream_branch = upstream_branch.replace("refs/heads/", "")

        # Build trailer for commits
        pr_url = f"https://github.com/{self.freebsd_src_repo}/pull/{pr_number}"
        trailers = (
            f'--trailer "Reviewed-by: {reviewer}" --trailer "Pull-Request: {pr_url}"'
        )

        # Determine editor command
        if not editor:
            editor = Path.home() / "bin" / "git-fixup-editor"
            noop_editor = "true"
            editor = str(editor) if editor.exists() else noop_editor

        exec_cmd = f"env EDITOR={editor} git commit --amend {trailers}"

        # Rebase onto staging with commit amendments
        LOGGER.info("Rebasing %s onto %s", pr_branch, self.staging_branch)
        try:
            self.githelper.rebase(
                base,
                onto=self.staging_branch,
                interactive=True,
                exec_cmd=exec_cmd,
            )
        except git.exc.GitCommandError:
            click.echo("\n" + "=" * 70)
            click.echo("REBASE FAILED - Conflicts need to be resolved")
            click.echo("=" * 70)
            click.echo("\nTo resolve:")
            click.echo("  1. Fix conflicts in the affected files")
            click.echo("  2. Stage resolved files: git add <files>")
            click.echo(f"  3. Continue staging: ghpr stage --continue {pr_number}")
            click.echo("\nOr to abort:")
            click.echo("  git rebase --abort")
            click.echo("=" * 70)
            sys.exit(1)

        # Save PR metadata
        self.gitconfig.set(f"{self.config_prefix}.prs", str(pr_number), add=True)
        if upstream:
            self.gitconfig.set(
                f"{self.config_prefix}.{pr_number}.upstream",
                upstream,
                add=True,
            )
        if upstream_branch:
            self.gitconfig.set(
                f"{self.config_prefix}.{pr_number}.upstream-branch",
                upstream_branch,
                add=True,
            )

        # Move staging branch to new tip
        LOGGER.info("Moving %s to include PR #%d", pr_branch, pr_number)
        self.githelper.move_branch(self.staging_branch)

        self._checkstyle(base, self.staging_branch)

        # Add label to GitHub PR
        LOGGER.info("Adding %r label to PR #%d...", STAGED_LABEL, pr_number)
        try:
            self.ghhelper.pr_edit(pr_number, add_label=STAGED_LABEL)
        except Exception:
            LOGGER.warning(
                "could not add %r label to PR #%d",
                STAGED_LABEL,
                pr_number,
                exc_info=True,
            )

        # Show review information
        try:
            pr_info = self.ghhelper.pr_view(pr_number)
            reviews = pr_info.get("reviews", [])
            approvers = [
                r["author"]["login"] for r in reviews if r["state"] == "APPROVED"
            ]
            if approvers:
                # Remove duplicates while preserving order
                seen = set()
                unique_approvers = []
                for approver in approvers:
                    if approver not in seen:
                        seen.add(approver)
                        unique_approvers.append(approver)
                LOGGER.info("Approved by: %r", unique_approvers)
        except Exception:
            LOGGER.warning("could not fetch review information", exc_info=True)

        LOGGER.info("PR #%d was staged successfully!", pr_number)
        LOGGER.info("Review the commits and when ready run 'ghpr push'!")

    def push(self: "Self", do_pr_branch_push: bool = False) -> None:
        """Push staged changes to FreeBSD and update GitHub (ghpr-push.sh)."""
        if not self.is_initialized():
            self.die(f"Branch {self.staging_branch} has not been initialized")

        prs = self.get_prs()
        if not prs and not self.dry_run:
            self.die(f"No PRs staged in {self.staging_branch}")

        def _push_step_one() -> None:
            """Step 1. rebase and push the PR to main."""
            if self.dry_run:
                click.echo(
                    f"DRY RUN: Step 1: Would push {len(prs)} PR(s) to FreeBSD main "
                    "branch...",
                )
                return

            click.echo(f"Pushing {len(prs)} PR(s) to FreeBSD main branch...")

            # Push loop - retry on failure with rebase
            while True:
                # Optional: push to PR branches (experimental feature)
                if do_pr_branch_push:
                    for pr in prs:
                        upstream = self.gitconfig.get(
                            f"{self.config_prefix}.{pr}.upstream",
                        )
                        upstream_branch = self.gitconfig.get(
                            f"{self.config_prefix}.{pr}.upstream-branch",
                        )
                        if upstream and upstream_branch:
                            click.echo(f"Pushing to PR #{pr} branch...")
                            self.githelper.push(
                                upstream,
                                f"HEAD:{upstream_branch}",
                                force=True,
                            )

                # Push to FreeBSD main
                click.echo("Pushing to FreeBSD main...")
                if self.ghhelper.push(
                    self.staging_remote,
                    "HEAD:main",
                    push_option="confirm-author",
                ):
                    break

                # Push failed, rebase and retry
                click.echo("Push failed, fetching and rebasing...")
                self.githelper.fetch(self.staging_remote)
                try:
                    self.githelper.rebase("freebsd/main")
                except git.exc.GitCommandError:
                    self.die("Rebase failed. Please resolve conflicts manually.")

            click.echo("Successfully pushed to FreeBSD main!")

        def _push_step_two() -> None:
            """Step 2. Update local main branch."""
            if self.dry_run:
                click.echo("DRY RUN: Step 2. Would update local main branch.")
                return

            click.echo("Step 2. Updating local main branch...")
            self.githelper.checkout(self.base)
            self.githelper.pull(rebase=True)

        def _push_step_three() -> None:
            """Step 3. Cleanup PRs post-push/-rebase."""
            if self.dry_run:
                click.echo("\nDRY RUN: Step 3. Would clean up PRs.")
                return

            click.echo("\nStep 3: Cleaning up PRs...")
            for pr in prs:
                pr_num = int(pr)
                if not do_pr_branch_push:
                    click.echo(f"Updating GitHub PR #{pr}...")
                    try:
                        # Remove staged label and add merged label
                        comment = (
                            "Automated message from ghpr: "
                            "Thank you for your submission. "
                            "This PR has been merged to FreeBSD's `main` branch. "
                            "These changes will appear shortly on our GitHub mirror."
                        )
                        self.ghhelper.pr_edit(
                            pr_num,
                            add_label=MERGED_LABEL,
                            remove_label=STAGED_LABEL,
                        )
                        self.ghhelper.pr_close(
                            pr_num,
                            comment=comment,
                        )
                    except Exception:
                        LOGGER.warning("failed to update PR #%d", pr, exc_info=True)

                # Delete PR branch
                self.gitconfig.delete_branch(self._pr_branch(pr))

                # Remove PR config
                self.gitconfig.remove_section(f"{self.config_prefix}.{pr}")

            # Remove staging branch config and branch
            self.gitconfig.remove_section(self.config_prefix)
            self.gitconfig.delete_branch(self.staging_branch)

        _push_step_one()
        _push_step_two()
        _push_step_three()

        if self.dry_run:
            click.echo(f"\nWould have landed {len(prs)} PR(s)!")
        else:
            click.echo(f"\nSuccessfully landed {len(prs)} PR(s)!")

    def unstage(self: "Self", pr_number: int) -> None:
        """Remove a staged PR from the staging branch."""
        if not self.is_initialized():
            self.die(f"Branch {self.staging_branch} has not been initialized")

        prs = self.get_prs()
        pr_str = str(pr_number)

        if pr_str not in prs and not self.dry_run:
            self.die(f"PR #{pr_number} is not staged")

        base = self.get_base()

        click.echo(f"Removing PR #{pr_number} from {self.staging_branch}...")

        # Find commits that belong to this PR by looking for the Pull Request trailer
        # Note: Git normalizes "Pull-Request" to "Pull Request" in trailers
        pr_commits = self.githelper.get_commits_with_trailer(
            base,
            self.staging_branch,
            "Pull Request",
            str(pr_number),
        )

        if not pr_commits:
            LOGGER.warning(
                "no commits found with Pull-Request trailer for #%d. "
                "The PR may have been manually rebased. "
                "Proceeding with config cleanup only",
                pr_number,
            )
        else:
            LOGGER.info("Found %d commit(s) for PR #%d", len(pr_commits), pr_number)

            # Get all commits in staging
            output = self.githelper.log(
                ["--format=%H", f"{base}..{self.staging_branch}"],
                capture=True,
                strip_newline_in_stdout=True,
                with_extended_output=False,
            )
            all_commits = [
                line.strip()
                for line in output.splitlines(keepends=False)
                if line.strip()
            ]

            # Filter out the PR's commits
            remaining_commits = [c for c in all_commits if c not in pr_commits]

            if not remaining_commits:
                # No commits left, just reset to base
                LOGGER.info(
                    "no commits remaining, resetting %s to %s",
                    self.staging_branch,
                    base,
                )
                self.githelper.reset(["--hard", base])
            else:
                # Rebuild staging branch without the PR's commits
                LOGGER.info(
                    "rebuilding %s without PR #%d... ",
                    self.staging_branch,
                    pr_number,
                )

                # Create a temporary branch at base
                temp_branch = f"temp-unstage-{pr_number}"
                self.githelper.checkout(base)
                self.githelper.checkout(temp_branch, create=True, base=base)

                # Cherry-pick the remaining commits in reverse order (oldest first)
                remaining_commits.reverse()
                try:
                    self.githelper.cherry_pick(remaining_commits)
                except git.exc.GitCommandError:
                    self.githelper.delete_branch(temp_branch, check=False)
                    self.die(
                        "Failed to cherry-pick remaining commits. "
                        "You may need to manually rebase the staging branch.",
                    )

                # Move staging to the new tree
                self.githelper.branch(["-f", self.staging_branch, temp_branch])
                self.githelper.checkout(self.staging_branch)
                self.githelper.delete_branch(temp_branch)

        # Delete PR branch if it exists
        self.githelper.delete_branch(self._pr_branch(pr_number), check=False)

        # Remove from config
        self.gitconfig.unset(f"{self.config_prefix}.prs", pr_str)
        self.gitconfig.remove_section(f"{self.config_prefix}.{pr_number}")

        # Remove 'staged' label from GitHub PR
        click.echo(f"Removing {STAGED_LABEL!r} label from PR #{pr_number}...")
        try:
            self.ghhelper.pr_edit(pr_number, remove_label=STAGED_LABEL)
        except Exception:
            LOGGER.warning(
                "failed to remove %r label from PR #%d",
                STAGED_LABEL,
                pr_number,
                exc_info=True,
            )

        click.echo(f"Successfully unstaged PR #{pr_number}")

        # Show updated status
        remaining_prs = self.get_prs()
        if remaining_prs:
            click.echo(
                f"\nRemaining PRs: {', '.join(['#' + pr for pr in remaining_prs])}",
            )
        else:
            click.echo("\nNo PRs remaining in staging branch")

    def status(self) -> None:
        """Show status of staging branch."""
        if not self.is_initialized():
            click.echo(f"Staging branch {self.staging_branch!r} is not initialized")
            click.echo("Run 'ghpr init' to initialize it")
            sys.exit(2)

        base = self.get_base()
        prs = self.get_prs()

        click.echo(f"Staging branch: {self.staging_branch}")
        click.echo(f"Base branch:    {base}")
        click.echo(f"PRs staged:     {len(prs)}")

        if prs:
            click.echo("\nStaged PRs:")
            for pr in prs:
                upstream = self.gitconfig.get(f"{self.config_prefix}.{pr}.upstream")
                upstream_branch = self.gitconfig.get(
                    f"{self.config_prefix}.{pr}.upstream-branch",
                )
                click.echo(f"  PR #{pr}")
                if upstream:
                    click.echo(f"    Upstream: {upstream}")
                if upstream_branch:
                    click.echo(f"    Branch:   {upstream_branch}")


pass_ghpr = click.make_pass_decorator(GHPR)


@click.group
@click.option(
    "--dry-run",
    default=False,
    is_flag=True,
    help=(
        "Show what would be done without actually doing it "
        "(automatically prints commands)"
    ),
)
@click.option(
    "--freebsd-src-repo",
    default=DEFAULT_FREEBSD_SRC_GITHUB_REPO,
    help="GitHub repository name (default: %(default)s)",
)
@click.option(
    "--staging-branch",
    default=DEFAULT_STAGING_BRANCH,
    help="Branch to use when staging changes (default: %(default)s)",
)
@click.option(
    "--staging-remote",
    default=DEFAULT_STAGING_REMOTE,
    help="Name of remote used for `--staging-branch` (default: %(default)s)",
)
@click.option("--verbose", default=False, is_flag=True)
@click.option(
    "--work-dir",
    type=click.Path(dir_okay=True, exists=True, file_okay=False),
)
@click.version_option(__version__)
@click.pass_context
def cli(
    ctx: click.Context,
    dry_run: bool,
    freebsd_src_repo: str,
    staging_branch: str,
    staging_remote: str,
    verbose: bool,
    work_dir: click.Path | None,
) -> None:
    r"""GitHub Pull Request landing tool for FreeBSD.

    Examples:
        # Initialize staging branch\n
            % ghpr init

        # Stage a PR (1234) for landing.\n
            % ghpr stage 1234

        # If a rebase has conflicts, resolve them and continue.\n
            % git add <resolved-files>\n
            % ghpr stage --continue 1234

        # Stage multiple PRs (1234 and 1235)\n
            % ghpr stage 1234\n
            % ghpr stage 1235\n

        # Check status\n
            % ghpr status

        # Unstage PR #1234 if you change your mind\n
            % ghpr unstage 1234

        # Push all staged PRs to FreeBSD\n
            % ghpr push

    """
    if dry_run:
        click.echo("DRY RUN MODE - No changes will be made\n")

    if work_dir is None:
        work_dir = Path.cwd()

    ctx.obj = GHPR(
        dry_run=dry_run,
        freebsd_src_repo=freebsd_src_repo,
        staging_branch=staging_branch,
        staging_remote=staging_remote,
        verbose=verbose,
        work_dir=work_dir,
    )


@cli.command
@click.option(
    "--force",
    default=False,
    is_flag=True,
    help="Force re-initialization: delete existing staging branch and config",
)
@pass_ghpr
def init(ghpr: GHPR, force: bool) -> None:
    """Initialize staging branch."""
    ghpr.init(force=force)


@cli.command
@click.option(
    "--pr-branch-push",
    is_flag=True,
    help="Also push to PR branches (experimental)",
)
@pass_ghpr
def push(ghpr: GHPR, pr_branch_push: bool) -> None:
    """Push staged PRs to FreeBSD."""
    ghpr.push(do_pr_branch_push=pr_branch_push)


@cli.command
@click.argument("pr", required=True, type=int)
@click.option(
    "--reviewer",
    default=getpass.getuser(),
    help="Reviewer name for Reviewed-by trailer (default: %(default)s)",
)
@click.option("--editor", default=None, help="Editor for commit message fixups")
@click.option(
    "--continue",
    "do_continue",
    default=False,
    is_flag=True,
    help="Continue an interrupted rebase",
)
@click.option(
    "--force",
    default=False,
    is_flag=True,
    help="Force staging even if PR is already marked as staged",
)
@pass_ghpr
def stage(
    ghpr: GHPR,
    pr: int,
    reviewer: str | None,
    editor: str | None,
    do_continue: bool,
    force: bool,
) -> None:
    """Stage a PR for landing."""
    ghpr.stage(
        pr,
        do_continue=do_continue,
        editor=editor,
        force=force,
        reviewer=reviewer,
    )


@cli.command
@click.argument("pr", required=True, type=int)
@pass_ghpr
def unstage(ghpr: GHPR, pr: int) -> None:
    """Remove a staged PR."""
    ghpr.unstage(pr)


@cli.command
@pass_ghpr
def status(ghpr: GHPR) -> None:
    """Show staging branch status."""
    ghpr.status()
