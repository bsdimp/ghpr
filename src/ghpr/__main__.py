"""ghpr - GitHub Pull Request landing tool for FreeBSD.

Unified tool to land GitHub pull requests into FreeBSD repositories.
Combines the functionality of ghpr-init.sh, ghpr-stage.sh, and ghpr-push.sh.

Copyright (c) 2026 Warner Losh <imp@FreeBSD.org>
Copyright (c) 2026 Enji Cooper <ngie@FreeBSD.org>

SPDX-License-Identifier: BSD-2-Clause
"""

# These issues are [generally] annoying noise from `ruff`.
#
# ruff: noqa: BLE001, FBT001, FBT002, S603

# These issues should be fixed.
#
# ruff: noqa: C901, PLR0912, PLR0913, PLR0915

from __future__ import annotations

import contextlib
import getpass
import json
import subprocess
import sys
import traceback
from pathlib import Path

import click

from . import __version__, logging

DEFAULT_FREEBSD_SRC_GITHUB_REPO = "freebsd/freebsd-src"
DEFAULT_STAGING_BRANCH = "staging"
DEFAULT_STAGING_REMOTE = "freebsd"
LOGGER = logging.get_logger("ghpr")

ALLOWED_STAGING_URLS = [
    "git@gitrepo.freebsd.org:src.git",
    "ssh://git@gitrepo.freebsd.org/src.git",
]


class GitConfig:
    """Helper class for git config operations."""

    verbose = False
    dry_run = False

    @staticmethod
    def _print_cmd(cmd: list[str]) -> None:
        """Print command if verbose or dry-run mode is enabled."""
        if GitConfig.verbose or GitConfig.dry_run:
            click.echo(f"+ {' '.join(cmd)}")

    @staticmethod
    def get(key: str, default: str | None = None) -> str | None:
        """Get a git config value."""
        cmd = ["git", "config", "--get", key]
        GitConfig._print_cmd(cmd)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return default

    @staticmethod
    def get_all(key: str) -> list[str]:
        """Get all values for a git config key."""
        cmd = ["git", "config", "--get-all", key]
        GitConfig._print_cmd(cmd)
        if GitConfig.dry_run:
            return []
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,  # The section might not exist
            text=True,
        )
        return [
            line.strip()
            for line in result.stdout.strip().splitlines(keepends=False)
            if line.strip()
        ]

    @staticmethod
    def set(
        key: str,
        value: str,
        config_type: str | None = None,
        add: bool = False,
    ) -> None:
        """Set a git config value."""
        cmd = ["git", "config"]
        if config_type:
            cmd.extend(["--type", config_type])
        if add:
            cmd.append("--add")
        cmd.extend([key, value])
        GitConfig._print_cmd(cmd)
        if GitConfig.dry_run:
            return
        subprocess.run(cmd, check=True)

    @staticmethod
    def unset(key: str, value: str | None = None) -> None:
        """Unset a git config value."""
        cmd = ["git", "config", "--unset"]
        cmd.append(key)
        if value:
            cmd.append(value)
        GitConfig._print_cmd(cmd)
        if GitConfig.dry_run:
            return
        with contextlib.suppress(subprocess.CalledProcessError):  # Key might not exist
            subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)

    @staticmethod
    def remove_section(section: str) -> None:
        """Remove a git config section."""
        cmd = ["git", "config", "--remove-section", section]
        GitConfig._print_cmd(cmd)
        if GitConfig.dry_run:
            return
        subprocess.run(
            cmd,
            check=False,  # The section might not exist
            stderr=subprocess.DEVNULL,
        )


class GitHelper:
    """Helper class for git operations."""

    verbose = False
    dry_run = False

    @staticmethod
    def _print_cmd(cmd: list[str]) -> None:
        """Print command if verbose or dry-run mode is enabled."""
        if GitHelper.verbose or GitHelper.dry_run:
            click.echo(f"+ {' '.join(cmd)}")

    @staticmethod
    def run(
        args: list[str],
        check: bool = True,
        capture: bool = False,
        safe: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run a git command."""
        cmd = ["git", *args]
        GitHelper._print_cmd(cmd)
        if GitHelper.dry_run and not safe:
            # In dry-run mode, don't execute anything
            class FakeResult:
                stdout = ""
                stderr = ""
                returncode = 0

            return FakeResult()
        if capture:
            return subprocess.run(cmd, capture_output=True, text=True, check=check)
        return subprocess.run(cmd, check=check)

    @staticmethod
    def branch_exists(branch: str) -> bool:
        """Check if a branch exists."""
        cmd = ["git", "rev-parse", "--verify", branch]
        GitHelper._print_cmd(cmd)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
        )
        return proc.returncode == 0

    @staticmethod
    def checkout(branch: str, create: bool = False, base: str | None = None) -> None:
        """Checkout a branch, optionally creating it."""
        cmd = ["checkout"]
        if create:
            cmd.append("-b")
        cmd.append(branch)
        if base:
            cmd.append(base)
        GitHelper.run(cmd)

    @staticmethod
    def rebase(
        base: str,
        onto: str | None = None,
        interactive: bool = False,
        exec_cmd: str | None = None,
    ) -> None:
        """Rebase current branch."""
        cmd = ["rebase"]
        if interactive:
            cmd.append("-i")
        if onto:
            cmd.extend(["--onto", onto])
        if exec_cmd:
            cmd.extend(["--exec", exec_cmd])
        cmd.append(base)
        GitHelper.run(cmd)

    @staticmethod
    def push(
        remote: str,
        refspec: str,
        force: bool = False,
        push_option: str | None = None,
    ) -> bool:
        """Push to remote, return True if successful."""
        cmd = ["push"]
        if push_option:
            cmd.extend(["--push-option", push_option])
        if force:
            cmd.append("--force")
        cmd.extend([remote, refspec])
        try:
            GitHelper.run(cmd)
        except subprocess.CalledProcessError:
            return False
        else:
            return True

    @staticmethod
    def fetch(remote: str) -> None:
        """Fetch from remote."""
        GitHelper.run(["fetch", remote], safe=True)

    @staticmethod
    def pull(rebase: bool = True) -> None:
        """Pull from current upstream."""
        cmd = ["pull"]
        if rebase:
            cmd.append("--rebase")
        GitHelper.run(cmd)

    @staticmethod
    def delete_branch(branch: str, force: bool = True) -> None:
        """Delete a branch."""
        flag = "-D" if force else "-d"
        GitHelper.run(
            ["branch", flag, branch],
            check=False,  # The branch might not exist
        )

    @staticmethod
    def move_branch(branch: str, target: str = "HEAD") -> None:
        """Force-move a branch to a specific commit and check it out."""
        # Force-move the branch pointer
        GitHelper.run(["branch", "-f", branch, target])
        # Check out the branch
        GitHelper.run(["checkout", branch])

    @staticmethod
    def get_commits_with_trailer(
        base: str,
        head: str,
        trailer: str,
        value: str,
    ) -> list[str]:
        """Get commit hashes that contain a specific trailer value."""
        cmd = [
            "log",
            "--format=%H",
            "--grep",
            f"^{trailer}: .*{value}",
            f"{base}..{head}",
        ]
        result = GitHelper.run(cmd, capture=True, safe=True)
        return [
            line.strip()
            for line in result.stdout.strip().splitlines(keepends=False)
            if line.strip()
        ]

    @staticmethod
    def cherry_pick(commits: list[str]) -> None:
        """Cherry-pick commits."""
        cmd = ["cherry-pick"]
        cmd.extend(commits)
        GitHelper.run(cmd)


class GHHelper:
    """Helper class for GitHub CLI operations."""

    verbose = False
    dry_run = False

    @staticmethod
    def _print_cmd(cmd: list[str]) -> None:
        """Print command if verbose or dry-run mode is enabled."""
        if GHHelper.verbose or GHHelper.dry_run:
            click.echo(f"+ {' '.join(cmd)}")

    @staticmethod
    def pr_checkout(pr_number: int, branch: str) -> None:
        """Checkout a PR into a branch."""
        cmd = [
            "gh",
            "pr",
            "--repo",
            DEFAULT_FREEBSD_SRC_GITHUB_REPO,
            "checkout",
            str(pr_number),
            "-b",
            branch,
        ]
        GHHelper._print_cmd(cmd)
        if GHHelper.dry_run:
            return
        subprocess.run(cmd, check=True)

    @staticmethod
    def gh_pr(
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
            "gh",
            "pr",
            "--repo",
            DEFAULT_FREEBSD_SRC_GITHUB_REPO,
            command,
            str(pr),
            *args,
        ]
        GHHelper._print_cmd(cmd)
        if GHHelper.dry_run:
            return None
        return subprocess.run(cmd, capture_output=True, check=True, text=True)

    @staticmethod
    def pr_edit(
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
        GHHelper.gh_pr("edit", pr_number, args)

    @staticmethod
    def pr_close(pr_number: int, comment: str | None = None) -> None:
        """Close a PR."""
        args = ["--comment", comment] if comment else []
        GHHelper.gh_pr("close", pr_number, args)

    @staticmethod
    def pr_view(pr_number: int) -> dict:
        """Get PR information including labels, assignees, and reviews."""
        if GHHelper.dry_run:
            return {"labels": [], "assignees": [], "reviews": []}
        args = [
            "--json",
            "labels,assignees,reviews",
        ]
        result = GHHelper.gh_pr("view", pr_number, args)
        return json.loads(result.stdout)


class GHPR:
    """Main class for GitHub PR landing operations."""

    def __init__(  # noqa: D107
        self,
        staging_branch: str = DEFAULT_STAGING_BRANCH,
        staging_remote: str = DEFAULT_STAGING_REMOTE,
        verbose: bool = False,
        dry_run: bool = False,
    ) -> None:
        self.base = "main"

        # Set verbose and dry_run on all helper classes
        GitConfig.verbose = verbose
        GitConfig.dry_run = dry_run
        GitHelper.verbose = verbose
        GitHelper.dry_run = dry_run
        GHHelper.verbose = verbose
        GHHelper.dry_run = dry_run

        self.staging = staging_branch
        self.staging_remote = staging_remote

        self.config_prefix = f"branch.{self.staging}.opabinia"

        self.verbose = verbose
        self.dry_run = dry_run
        if dry_run:
            click.echo("DRY RUN MODE - No changes will be made\n")

    @staticmethod
    def die(message: str) -> None:
        """Print error and exit."""
        sys.exit(f"Error: {message}")

    def is_initialized(self) -> bool:
        """Check if staging branch is initialized."""
        return GitConfig.get(self.config_prefix) == "true"

    def get_base(self) -> str:
        """Get the base branch for staging."""
        base = GitConfig.get(f"{self.config_prefix}.base")
        if not base:
            self.die(f"No base set on {self.staging}")
        return base

    def get_prs(self) -> list[str]:
        """Get list of PRs in staging branch."""
        return GitConfig.get_all(f"{self.config_prefix}.prs")

    def _check_staging_remote(self) -> None:
        """Verify the staging remote.

        Confirm that the staging branch remote:
        - .. exists.
        - .. points to one of the expected URLs.
        """
        # Check if remote exists
        try:
            result = GitHelper.run(
                ["remote", "get-url", self.staging_remote],
                capture=True,
                check=True,
                safe=True,
            )
        except subprocess.CalledProcessError:
            self.die(
                f"No {self.staging_remote!r} remote found.\n"
                f"Please add it with:\n"
                f"  git remote add {self.staging_remote} {ALLOWED_STAGING_URLS[0]}",
            )
        else:
            fetch_url = result.stdout.strip()

        # Check fetch URL
        if fetch_url not in ALLOWED_STAGING_URLS:
            self.die(
                f"{self.staging_remote!r} remote fetch URL is incorrect.\n"
                f"Allowed URLs: {ALLOWED_STAGING_URLS!r}\n"
                f"Got:      {fetch_url}\n"
                f"Please update it with:\n"
                f"  git remote set-url {self.staging_remote} {ALLOWED_STAGING_URLS[0]}",
            )

        # Check push URL
        try:
            result = GitHelper.run(
                ["remote", "get-url", "--push", self.staging_remote],
                capture=True,
                check=False,
                safe=True,
            )
            # If no separate push URL, it uses fetch URL
            push_url = result.stdout.strip() if result.returncode == 0 else fetch_url
        except Exception:
            push_url = fetch_url

        if push_url not in ALLOWED_STAGING_URLS:
            self.die(
                f"'{self.staging_remote}' remote push URL is incorrect.\n"
                f"Allowed URLs: {ALLOWED_STAGING_URLS!r}\n"
                f"Got:      {push_url}\n"
                f"Please update it with:\n"
                f"  git remote set-url --push {self.staging_remote} "
                f"{ALLOWED_STAGING_URLS[0]}",
            )

        if self.verbose:
            click.echo(f"✓ '{self.staging_remote}' remote is correctly configured")

    def init(self, force: bool = False) -> None:
        """Initialize staging branch for PR landing (ghpr-init.sh)."""
        # Check that the staging branch's remote is properly configured
        self._check_staging_remote()

        if force:
            click.echo("Force re-initialization requested")
            if self.is_initialized() or GitHelper.branch_exists(self.staging):
                click.echo(f"Cleaning up existing {self.staging} branch and config...")
                # Remove all config for this staging branch
                GitConfig.remove_section(self.config_prefix)
                # Checkout base branch if we're currently on staging
                # (can't delete a branch we're on)
                GitHelper.checkout(self.base)
                # Delete the branch if it exists
                GitHelper.delete_branch(self.staging)
                click.echo("Cleanup complete")

        if self.is_initialized():
            click.echo(f"Branch {self.staging} has already been initialized")
            return

        if GitHelper.branch_exists(self.staging):
            click.echo(
                f"Branch {self.staging} already exists. "
                f"Skipping creation, but rebasing to {self.base}",
            )
            GitHelper.rebase(self.base, interactive=False)
        else:
            click.echo(f"Creating {self.staging} from {self.base} to land changes")
            try:
                GitHelper.checkout(self.staging, create=True, base=self.base)
            except subprocess.CalledProcessError:
                click.echo(traceback.format_exc())
                self.die(f"Can't create {self.staging}")

        try:
            GitConfig.set(self.config_prefix, "true", config_type="bool")
            GitConfig.set(f"{self.config_prefix}.base", self.base)
        except subprocess.CalledProcessError:
            click.echo(traceback.format_exc())
            self.die("Can't annotate branch config")

        click.echo(f"Staging branch {self.staging} initialized successfully")

    def update_to_upstream(self) -> None:
        """Update base branch and rebase staging onto it."""
        click.echo(f"Updating {self.base} and rebasing {self.staging}...")
        GitHelper.checkout(self.base)
        GitHelper.pull(rebase=True)
        GitHelper.rebase(self.base, interactive=True)

    def _checkstyle(self, base: str, tip: str) -> None:
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
        try:
            subprocess.run(cmd, check=True)  # Don't fail on style issues
        except Exception:
            LOGGER.warning("style checker found issues (see output above)")

    def stage(
        self,
        pr_number: int,
        reviewer: str | None = None,
        repo: str = "freebsd-src",
        editor: str | None = None,
        do_continue: bool = False,
        force: bool = False,
    ) -> None:
        """Stage a PR for landing (ghpr-stage.sh)."""
        if not self.is_initialized():
            self.die(
                f"Branch {self.staging} has not been initialized. "
                "Run 'ghpr init' first.",
            )

        base = self.get_base()
        prs = self.get_prs()
        pr_branch = f"PR-{pr_number}"

        # Check if PR is already staged (unless --force or --continue)
        if not do_continue and not force:
            pr_str = str(pr_number)

            # First check if PR is already in our staging branch
            if pr_str in prs:
                LOGGER.error("PR #%d is already staged", pr_number)

                try:
                    pr_info = GHHelper.pr_view(pr_number)
                    # Show assignees if any
                    assignees = pr_info.get("assignees", [])
                    if assignees:
                        assignee_logins = [a["login"] for a in assignees]
                        LOGGER.info("Assigned to: %r", assignee_logins)
                except subprocess.CalledProcessError:
                    pass  # Continue even if we can't fetch PR info

                LOGGER.info("Use --force to stage anyway")
                sys.exit(1)

            # Check if PR has 'staged' label but isn't actually staged
            try:
                pr_info = GHHelper.pr_view(pr_number)
                labels = [label["name"] for label in pr_info.get("labels", [])]

                if "staged" in labels:
                    LOGGER.warning(
                        "PR #%d has 'staged' label but is not staged locally. "
                        "The label may be stale. Continuing with staging...",
                        pr_number,
                    )
            except subprocess.CalledProcessError:
                LOGGER.warning(
                    "Could not check PR status. Continuing with staging...",
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
                GitHelper.run(["rebase", "--continue"], check=True)
            except subprocess.CalledProcessError:
                self.die(
                    "Rebase continue failed. "
                    "Resolve conflicts and run 'ghpr stage --continue <PR>' again.",
                )

            # Save PR metadata if not already saved
            if str(pr_number) not in prs:
                upstream = GitConfig.get(f"branch.{pr_branch}.pushRemote")
                upstream_branch = GitConfig.get(f"branch.{pr_branch}.merge")
                if upstream_branch:
                    upstream_branch = upstream_branch.replace("refs/heads/", "")

                GitConfig.set(f"{self.config_prefix}.prs", str(pr_number), add=True)
                if upstream:
                    GitConfig.set(
                        f"{self.config_prefix}.{pr_number}.upstream",
                        upstream,
                        add=True,
                    )
                if upstream_branch:
                    GitConfig.set(
                        f"{self.config_prefix}.{pr_number}.upstream-branch",
                        upstream_branch,
                        add=True,
                    )

            # Move staging branch to new tip
            LOGGER.info("Moving %s to include PR #%d...", self.staging, pr_number)
            GitHelper.move_branch(self.staging)

            self._checkstyle(base, self.staging)

            # Add 'staged' label to GitHub PR
            LOGGER.info("Adding 'staged' label to PR #%d...", pr_number)
            try:
                GHHelper.pr_edit(pr_number, add_label="staged")
            except Exception:
                LOGGER.warning(
                    "failed to add 'staged' label to PR #%d",
                    pr_number,
                    exc_info=True,
                )

            # Show review information
            try:
                pr_info = GHHelper.pr_view(pr_number)
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
            GitHelper.checkout(self.staging)

        # Create PR branch
        LOGGER.info("Checking out PR #%d into %s", pr_number, pr_branch)

        # Delete old PR branch if it exists
        GitHelper.delete_branch(pr_branch)

        # Checkout the PR
        try:
            GHHelper.pr_checkout(pr_number, pr_branch)
        except subprocess.CalledProcessError:
            self.die(f"Failed to checkout PR #{pr_number}")

        # Get upstream info
        upstream = GitConfig.get(f"branch.{pr_branch}.pushRemote")
        upstream_branch = GitConfig.get(f"branch.{pr_branch}.merge")
        if upstream_branch:
            upstream_branch = upstream_branch.replace("refs/heads/", "")

        # Build trailer for commits
        pr_url = f"https://github.com/freebsd/{repo}/pull/{pr_number}"
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
        LOGGER.info("Rebasing %s onto %s", pr_branch, self.staging)
        try:
            GitHelper.rebase(
                base,
                onto=self.staging,
                interactive=True,
                exec_cmd=exec_cmd,
            )
        except subprocess.CalledProcessError:
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
        GitConfig.set(f"{self.config_prefix}.prs", str(pr_number), add=True)
        if upstream:
            GitConfig.set(
                f"{self.config_prefix}.{pr_number}.upstream",
                upstream,
                add=True,
            )
        if upstream_branch:
            GitConfig.set(
                f"{self.config_prefix}.{pr_number}.upstream-branch",
                upstream_branch,
                add=True,
            )

        # Move staging branch to new tip
        LOGGER.info("Moving %s to include PR #%d", pr_branch, pr_number)
        GitHelper.move_branch(self.staging)

        self._checkstyle(base, self.staging)

        # Add 'staged' label to GitHub PR
        LOGGER.info("Adding 'staged' label to PR #%d...", pr_number)
        try:
            GHHelper.pr_edit(pr_number, add_label="staged")
        except Exception:
            LOGGER.warning(
                "could not add 'staged' label to PR #%d",
                pr_number,
                exc_info=True,
            )

        # Show review information
        try:
            pr_info = GHHelper.pr_view(pr_number)
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

    def push(self, do_pr_branch_push: bool = False) -> None:
        """Push staged changes to FreeBSD and update GitHub (ghpr-push.sh)."""
        if not self.is_initialized():
            self.die(f"Branch {self.staging} has not been initialized")

        prs = self.get_prs()
        if not prs:
            self.die(f"No PRs staged in {self.staging}")

        click.echo(f"Pushing {len(prs)} PR(s) to FreeBSD main branch...")

        # Push loop - retry on failure with rebase
        while True:
            # Optional: push to PR branches (experimental feature)
            if do_pr_branch_push:
                for pr in prs:
                    upstream = GitConfig.get(f"{self.config_prefix}.{pr}.upstream")
                    upstream_branch = GitConfig.get(
                        f"{self.config_prefix}.{pr}.upstream-branch",
                    )
                    if upstream and upstream_branch:
                        click.echo(f"Pushing to PR #{pr} branch...")
                        GitHelper.push(upstream, f"HEAD:{upstream_branch}", force=True)

            # Push to FreeBSD main
            click.echo("Pushing to FreeBSD main...")
            if GitHelper.push(
                self.staging_remote,
                "HEAD:main",
                push_option="confirm-author",
            ):
                break

            # Push failed, rebase and retry
            click.echo("Push failed, fetching and rebasing...")
            GitHelper.fetch(self.staging_remote)
            try:
                GitHelper.rebase("freebsd/main")
            except subprocess.CalledProcessError:
                self.die("Rebase failed. Please resolve conflicts manually.")

        click.echo("Successfully pushed to FreeBSD main!")

        # Update local main
        click.echo("Updating local main branch...")
        GitHelper.checkout("main")
        GitHelper.pull(rebase=True)

        # Cleanup PRs
        click.echo("\nCleaning up...")
        for pr in prs:
            pr_num = int(pr)
            if not do_pr_branch_push:
                click.echo(f"Updating GitHub PR #{pr}...")
                try:
                    # Remove 'staged' label and add 'merged' label
                    comment = (
                        "Automated message from ghpr: Thank you for your submission. "
                        "This PR has been merged to FreeBSD's `main` branch. "
                        "These changes will appear shortly on our GitHub mirror."
                    )
                    GHHelper.pr_edit(pr_num, add_label="merged", remove_label="staged")
                    GHHelper.pr_close(
                        pr_num,
                        comment=comment,
                    )
                except Exception:
                    LOGGER.warning("failed to update PR #%d", pr, exc_info=True)

            # Delete PR branch
            GitHelper.delete_branch(f"PR-{pr}")

            # Remove PR config
            GitConfig.remove_section(f"{self.config_prefix}.{pr}")

        # Remove staging branch config and branch
        GitConfig.remove_section(self.config_prefix)
        GitHelper.delete_branch(self.staging)

        click.echo(f"\nSuccessfully landed {len(prs)} PR(s)!")

    def unstage(self, pr_number: int) -> None:
        """Remove a staged PR from the staging branch."""
        if not self.is_initialized():
            self.die(f"Branch {self.staging} has not been initialized")

        prs = self.get_prs()
        pr_str = str(pr_number)

        if pr_str not in prs:
            self.die(f"PR #{pr_number} is not staged")

        base = self.get_base()

        click.echo(f"Removing PR #{pr_number} from {self.staging}...")

        # Find commits that belong to this PR by looking for the Pull Request trailer
        # Note: Git normalizes "Pull-Request" to "Pull Request" in trailers
        pr_commits = GitHelper.get_commits_with_trailer(
            base,
            self.staging,
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
            result = GitHelper.run(
                ["log", "--format=%H", f"{base}..{self.staging}"],
                capture=True,
                safe=True,
            )
            all_commits = [
                line.strip()
                for line in result.stdout.strip().splitlines(keepends=False)
                if line.strip()
            ]

            # Filter out the PR's commits
            remaining_commits = [c for c in all_commits if c not in pr_commits]

            if not remaining_commits:
                # No commits left, just reset to base
                LOGGER.info(
                    "no commits remaining, resetting %s to %s",
                    self.staging,
                    base,
                )
                GitHelper.run(["reset", "--hard", base])
            else:
                # Rebuild staging branch without the PR's commits
                LOGGER.info("rebuilding %s without PR #%d... ", self.staging, pr_number)

                # Create a temporary branch at base
                temp_branch = f"temp-unstage-{pr_number}"
                GitHelper.checkout(base)
                GitHelper.checkout(temp_branch, create=True, base=base)

                # Cherry-pick the remaining commits in reverse order (oldest first)
                remaining_commits.reverse()
                try:
                    GitHelper.cherry_pick(remaining_commits)
                except subprocess.CalledProcessError:
                    GitHelper.delete_branch(temp_branch)
                    self.die(
                        "Failed to cherry-pick remaining commits. "
                        "You may need to manually rebase the staging branch.",
                    )

                # Move staging to the new tree
                GitHelper.run(["branch", "-f", self.staging, temp_branch])
                GitHelper.checkout(self.staging)
                GitHelper.delete_branch(temp_branch)

        # Delete PR branch if it exists
        GitHelper.delete_branch(f"PR-{pr_number}")

        # Remove from config
        GitConfig.unset(f"{self.config_prefix}.prs", pr_str)
        GitConfig.remove_section(f"{self.config_prefix}.{pr_number}")

        # Remove 'staged' label from GitHub PR
        click.echo(f"Removing 'staged' label from PR #{pr_number}...")
        try:
            GHHelper.pr_edit(pr_number, remove_label="staged")
        except Exception:
            LOGGER.warning(
                "Failed to remove 'staged' label from PR #%d",
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
            click.echo(f"Staging branch '{self.staging}' is not initialized")
            click.echo("Run 'ghpr init' to initialize it")
            sys.exit(2)

        base = self.get_base()
        prs = self.get_prs()

        click.echo(f"Staging branch: {self.staging}")
        click.echo(f"Base branch:    {base}")
        click.echo(f"PRs staged:     {len(prs)}")

        if prs:
            click.echo("\nStaged PRs:")
            for pr in prs:
                upstream = GitConfig.get(f"{self.config_prefix}.{pr}.upstream")
                upstream_branch = GitConfig.get(
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
    "--staging-branch",
    default=DEFAULT_STAGING_BRANCH,
)
@click.option(
    "--staging-remote",
    default=DEFAULT_STAGING_REMOTE,
    help="Name of remote used for `--staging-branch` (default: %(default)s)",
)
@click.option("--verbose", default=False, is_flag=True)
@click.version_option(__version__)
@click.pass_context
def cli(
    ctx: click.Context,
    dry_run: bool,
    staging_branch: str,
    staging_remote: str,
    verbose: bool,
) -> None:
    # ruff: noqa: D301
    """GitHub Pull Request landing tool for FreeBSD.

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

    ctx.obj = GHPR(
        staging_branch=staging_branch,
        staging_remote=staging_remote,
        dry_run=dry_run,
        verbose=verbose,
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
@click.option(
    "--repo",
    default="freebsd-src",
    help="GitHub repository name (default: %(default)s)",
)
@click.option("--editor", default=None, help="Editor for commit message fixups")
@click.option(
    "--continue",
    "do_continue",
    default=False,
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
    repo: str,
    editor: str | None,
    do_continue: bool,
    force: bool,
) -> None:
    """Stage a PR for landing."""
    ghpr.stage(
        pr,
        reviewer=reviewer,
        repo=repo,
        editor=editor,
        do_continue=do_continue,
        force=force,
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
