"""ghpr - GitHub Pull Request landing tool for FreeBSD.

Unified tool to land GitHub pull requests into FreeBSD repositories.
Combines the functionality of ghpr-init.sh, ghpr-stage.sh, and ghpr-push.sh.

Copyright (c) 2026 Warner Losh <imp@FreeBSD.org>
SPDX-License-Identifier: BSD-2-Clause
"""

# These issues are [generally] annoying noise from `ruff`.
#
# ruff: noqa: BLE001, FBT001, FBT002, S603, T201

# These issues should be fixed.
#
# ruff: noqa: C901, PLR0912, PLR0913, PLR0915

from __future__ import annotations

import argparse
import contextlib
import getpass
import json
import subprocess
import sys
from pathlib import Path

from . import __version__


class GitConfig:
    """Helper class for git config operations."""

    verbose = False
    dry_run = False

    @staticmethod
    def _print_cmd(cmd: list[str]) -> None:
        """Print command if verbose or dry-run mode is enabled."""
        if GitConfig.verbose or GitConfig.dry_run:
            print(f"+ {' '.join(cmd)}", file=sys.stderr)

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
            print(f"+ {' '.join(cmd)}", file=sys.stderr)

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
            print(f"+ {' '.join(cmd)}", file=sys.stderr)

    @staticmethod
    def pr_checkout(pr_number: int, branch: str) -> None:
        """Checkout a PR into a branch."""
        cmd = ["gh", "pr", "checkout", str(pr_number), "-b", branch]
        GHHelper._print_cmd(cmd)
        if GHHelper.dry_run:
            return
        subprocess.run(cmd, check=True)

    @staticmethod
    def pr_edit(
        pr_number: int,
        add_label: str | None = None,
        remove_label: str | None = None,
    ) -> None:
        """Edit PR metadata."""
        cmd = ["gh", "pr", "edit", str(pr_number)]
        if add_label:
            cmd.extend(["--add-label", add_label])
        if remove_label:
            cmd.extend(["--remove-label", remove_label])
        GHHelper._print_cmd(cmd)
        if GHHelper.dry_run:
            return
        subprocess.run(cmd, check=True)

    @staticmethod
    def pr_close(pr_number: int, comment: str | None = None) -> None:
        """Close a PR."""
        cmd = ["gh", "pr", "close", str(pr_number)]
        if comment:
            cmd.extend(["--comment", comment])
        GHHelper._print_cmd(cmd)
        if GHHelper.dry_run:
            return
        subprocess.run(cmd, check=True)

    @staticmethod
    def pr_view(pr_number: int) -> dict:
        """Get PR information including labels, assignees, and reviews."""
        cmd = ["gh", "pr", "view", str(pr_number), "--json", "labels,assignees,reviews"]
        GHHelper._print_cmd(cmd)
        if GHHelper.dry_run:
            return {"labels": [], "assignees": [], "reviews": []}
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)


class GHPR:
    """Main class for GitHub PR landing operations."""

    def __init__(  # noqa: D107
        self,
        staging_branch: str = "staging",
        verbose: bool = False,
        dry_run: bool = False,
    ) -> None:
        self.staging = staging_branch
        self.base = "main"
        self.config_prefix = f"branch.{self.staging}.opabinia"
        self.verbose = verbose
        self.dry_run = dry_run

        # Set verbose and dry_run on all helper classes
        GitConfig.verbose = verbose
        GitConfig.dry_run = dry_run
        GitHelper.verbose = verbose
        GitHelper.dry_run = dry_run
        GHHelper.verbose = verbose
        GHHelper.dry_run = dry_run

        if dry_run:
            print("DRY RUN MODE - No changes will be made\n", file=sys.stderr)

    def die(self, message: str) -> None:
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

    def _check_freebsd_remote(self) -> None:
        """Verify that 'freebsd' remote exists and points to the correct URL."""
        expected_url = "ssh://git@gitrepo.freebsd.org/src.git"

        # Check if remote exists
        try:
            result = GitHelper.run(
                ["remote", "get-url", "freebsd"],
                capture=True,
                check=False,
                safe=True,
            )
            if result.returncode != 0:
                self.die(
                    f"No 'freebsd' remote found.\n"
                    f"Please add it with:\n"
                    f"  git remote add freebsd {expected_url}",
                )
            fetch_url = result.stdout.strip()
        except Exception:
            self.die(
                f"Failed to check 'freebsd' remote.\n"
                f"Please ensure it exists and points to:\n"
                f"  {expected_url}",
            )

        # Check fetch URL
        if fetch_url != expected_url:
            self.die(
                f"'freebsd' remote fetch URL is incorrect.\n"
                f"Expected: {expected_url}\n"
                f"Got:      {fetch_url}\n"
                f"Please update it with:\n"
                f"  git remote set-url freebsd {expected_url}",
            )

        # Check push URL
        try:
            result = GitHelper.run(
                ["remote", "get-url", "--push", "freebsd"],
                capture=True,
                check=False,
                safe=True,
            )
            # If no separate push URL, it uses fetch URL
            push_url = result.stdout.strip if result.returncode == 0 else fetch_url
        except Exception:
            push_url = fetch_url

        if push_url != expected_url:
            self.die(
                f"'freebsd' remote push URL is incorrect.\n"
                f"Expected: {expected_url}\n"
                f"Got:      {push_url}\n"
                f"Please update it with:\n"
                f"  git remote set-url --push freebsd {expected_url}",
            )

        if self.verbose:
            print("✓ 'freebsd' remote is correctly configured", file=sys.stderr)

    def init(self, force: bool = False) -> None:
        """Initialize staging branch for PR landing (ghpr-init.sh)."""
        # Check that 'freebsd' remote is properly configured
        self._check_freebsd_remote()

        if force:
            print("Force re-initialization requested")
            if self.is_initialized() or GitHelper.branch_exists(self.staging):
                print(f"Cleaning up existing {self.staging} branch and config...")
                # Remove all config for this staging branch
                GitConfig.remove_section(self.config_prefix)
                # Checkout base branch if we're currently on staging
                # (can't delete a branch we're on)
                GitHelper.checkout(self.base)
                # Delete the branch if it exists
                GitHelper.delete_branch(self.staging)
                print("Cleanup complete")

        if self.is_initialized():
            print(f"Branch {self.staging} has already been initialized")
            return

        if GitHelper.branch_exists(self.staging):
            print(
                f"Branch {self.staging} already exists. "
                f"Skipping creation, but rebasing to {self.base}",
            )
            GitHelper.rebase(self.base, interactive=False)
        else:
            print(f"Creating {self.staging} from {self.base} to land changes")
            try:
                GitHelper.checkout(self.staging, create=True, base=self.base)
            except subprocess.CalledProcessError:
                self.die(f"Can't create {self.staging}")

        try:
            GitConfig.set(self.config_prefix, "true", config_type="bool")
            GitConfig.set(f"{self.config_prefix}.base", self.base)
        except subprocess.CalledProcessError:
            self.die("Can't annotate branch config")

        print(f"Staging branch {self.staging} initialized successfully")

    def update_to_upstream(self) -> None:
        """Update base branch and rebase staging onto it."""
        print(f"Updating {self.base} and rebasing {self.staging}...")
        GitHelper.checkout(self.base)
        GitHelper.pull(rebase=True)
        GitHelper.rebase(self.base, interactive=True)

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
                print(f"Error: PR #{pr_number} is already staged", file=sys.stderr)

                try:
                    pr_info = GHHelper.pr_view(pr_number)
                    # Show assignees if any
                    assignees = pr_info.get("assignees", [])
                    if assignees:
                        assignee_logins = [a["login"] for a in assignees]
                        print(
                            f"Assigned to: {', '.join(assignee_logins)}",
                            file=sys.stderr,
                        )
                except subprocess.CalledProcessError:
                    pass  # Continue even if we can't fetch PR info

                print("\nUse --force to stage anyway", file=sys.stderr)
                sys.exit(1)

            # Check if PR has 'staged' label but isn't actually staged
            try:
                pr_info = GHHelper.pr_view(pr_number)
                labels = [label["name"] for label in pr_info.get("labels", [])]

                if "staged" in labels:
                    print(
                        f"Warning: PR #{pr_number} has 'staged' label but is not "
                        "staged locally",
                        file=sys.stderr,
                    )
                    print(
                        "The label may be stale. Continuing with staging...",
                        file=sys.stderr,
                    )
            except subprocess.CalledProcessError as e:
                print(f"Warning: Could not check PR status: {e}", file=sys.stderr)
                print("Continuing with staging...", file=sys.stderr)

        # Handle --continue for interrupted rebase
        if do_continue:
            print(f"Continuing interrupted rebase for PR #{pr_number}...")

            # Check if we're in a rebase
            git_dir = Path(".git")
            rebase_merge = git_dir / "rebase-merge"
            rebase_apply = git_dir / "rebase-apply"

            if not (rebase_merge.exists() or rebase_apply.exists()):
                self.die("No rebase in progress. Cannot continue.")

            # Continue the rebase
            try:
                GitHelper.run(["rebase", "--continue"])
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
            print(f"Moving {self.staging} to include PR #{pr_number}")
            GitHelper.move_branch(self.staging)

            # Run style checker if it exists
            checkstyle = Path("tools/build/checkstyle9.pl")
            if checkstyle.exists():
                print("Running style checker...")
                cmd = ["perl", str(checkstyle), f"{base}..{self.staging}"]
                if self.verbose or self.dry_run:
                    print(f"+ {' '.join(cmd)}", file=sys.stderr)
                if not self.dry_run:
                    try:
                        subprocess.run(cmd, check=False)  # Don't fail on style issues
                    except Exception as e:
                        print(f"Style checker warning: {e}")

            # Add 'staged' label to GitHub PR
            print(f"Adding 'staged' label to PR #{pr_number}...")
            try:
                GHHelper.pr_edit(pr_number, add_label="staged")
            except Exception as e:
                print(f"Warning: Failed to add 'staged' label to PR #{pr_number}: {e}")

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
                    print(f"\nApproved by: {', '.join(unique_approvers)}")
            except Exception as e:
                print(
                    f"Warning: Could not fetch review information: {e}",
                    file=sys.stderr,
                )

            print(f"\nPR #{pr_number} staged successfully!")
            print("Review the commits and when ready, run: ghpr push")
            return

        # Normal staging flow (not --continue)

        # Update to upstream if no PRs staged yet
        if not prs:
            self.update_to_upstream()
        else:
            GitHelper.checkout(self.staging)

        # Create PR branch
        print(f"Checking out PR #{pr_number} into {pr_branch}...")

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
        print(f"Rebasing {pr_branch} onto {self.staging}...")
        try:
            GitHelper.rebase(
                base,
                onto=self.staging,
                interactive=True,
                exec_cmd=exec_cmd,
            )
        except subprocess.CalledProcessError:
            print("\n" + "=" * 70)
            print("REBASE FAILED - Conflicts need to be resolved")
            print("=" * 70)
            print("\nTo resolve:")
            print("  1. Fix conflicts in the affected files")
            print("  2. Stage resolved files: git add <files>")
            print(f"  3. Continue staging: ghpr stage --continue {pr_number}")
            print("\nOr to abort:")
            print("  git rebase --abort")
            print("=" * 70)
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
        print(f"Moving {self.staging} to include PR #{pr_number}")
        GitHelper.move_branch(self.staging)

        # Run style checker if it exists
        checkstyle = Path("tools/build/checkstyle9.pl")
        if checkstyle.exists():
            print("Running style checker...")
            cmd = ["perl", str(checkstyle), f"{base}..{self.staging}"]
            if self.verbose or self.dry_run:
                print(f"+ {' '.join(cmd)}", file=sys.stderr)
            if not self.dry_run:
                try:
                    subprocess.run(cmd, check=False)  # Don't fail on style issues
                except Exception as e:
                    print(f"Style checker warning: {e}")

        # Add 'staged' label to GitHub PR
        print(f"Adding 'staged' label to PR #{pr_number}...")
        try:
            GHHelper.pr_edit(pr_number, add_label="staged")
        except Exception as e:
            print(f"Warning: Failed to add 'staged' label to PR #{pr_number}: {e}")

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
                print(f"\nApproved by: {', '.join(unique_approvers)}")
        except Exception as e:
            print(f"Warning: Could not fetch review information: {e}", file=sys.stderr)

        print(f"\nPR #{pr_number} staged successfully!")
        print("Review the commits and when ready, run: ghpr push")

    def push(self, do_pr_branch_push: bool = False) -> None:
        """Push staged changes to FreeBSD and update GitHub (ghpr-push.sh)."""
        if not self.is_initialized():
            self.die(f"Branch {self.staging} has not been initialized")

        prs = self.get_prs()
        if not prs:
            self.die(f"No PRs staged in {self.staging}")

        print(f"Pushing {len(prs)} PR(s) to FreeBSD main branch...")

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
                        print(f"Pushing to PR #{pr} branch...")
                        GitHelper.push(upstream, f"HEAD:{upstream_branch}", force=True)

            # Push to FreeBSD main
            print("Pushing to FreeBSD main...")
            if GitHelper.push("freebsd", "HEAD:main", push_option="confirm-author"):
                break

            # Push failed, rebase and retry
            print("Push failed, fetching and rebasing...")
            GitHelper.fetch("freebsd")
            try:
                GitHelper.rebase("freebsd/main")
            except subprocess.CalledProcessError:
                self.die("Rebase failed. Please resolve conflicts manually.")

        print("Successfully pushed to FreeBSD main!")

        # Update local main
        print("Updating local main branch...")
        GitHelper.checkout("main")
        GitHelper.pull(rebase=True)

        # Cleanup PRs
        print("\nCleaning up...")
        for pr in prs:
            pr_num = int(pr)
            if not do_pr_branch_push:
                print(f"Updating GitHub PR #{pr}...")
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
                except Exception as e:
                    print(f"Warning: Failed to update PR #{pr}: {e}")

            # Delete PR branch
            GitHelper.delete_branch(f"PR-{pr}")

            # Remove PR config
            GitConfig.remove_section(f"{self.config_prefix}.{pr}")

        # Remove staging branch config and branch
        GitConfig.remove_section(self.config_prefix)
        GitHelper.delete_branch(self.staging)

        print(f"\nSuccessfully landed {len(prs)} PR(s)!")

    def unstage(self, pr_number: int) -> None:
        """Remove a staged PR from the staging branch."""
        if not self.is_initialized():
            self.die(f"Branch {self.staging} has not been initialized")

        prs = self.get_prs()
        pr_str = str(pr_number)

        if pr_str not in prs:
            self.die(f"PR #{pr_number} is not staged")

        base = self.get_base()

        print(f"Removing PR #{pr_number} from {self.staging}...")

        # Find commits that belong to this PR by looking for the Pull Request trailer
        # Note: Git normalizes "Pull-Request" to "Pull Request" in trailers
        pr_commits = GitHelper.get_commits_with_trailer(
            base,
            self.staging,
            "Pull Request",
            str(pr_number),
        )

        if not pr_commits:
            print(
                f"Warning: No commits found with Pull-Request trailer for #{pr_number}",
            )
            print(
                "The PR may have been manually rebased. "
                "Proceeding with config cleanup only.",
            )
        else:
            print(f"Found {len(pr_commits)} commit(s) for PR #{pr_number}")

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
                print(f"No commits remaining, resetting {self.staging} to {base}")
                GitHelper.run(["reset", "--hard", base])
            else:
                # Rebuild staging branch without the PR's commits
                print(f"Rebuilding {self.staging} without PR #{pr_number}...")

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
        print(f"Removing 'staged' label from PR #{pr_number}...")
        try:
            GHHelper.pr_edit(pr_number, remove_label="staged")
        except Exception as e:
            print(f"Warning: Failed to remove 'staged' label from PR #{pr_number}: {e}")

        print(f"Successfully unstaged PR #{pr_number}")

        # Show updated status
        remaining_prs = self.get_prs()
        if remaining_prs:
            print(f"\nRemaining PRs: {', '.join(['#' + pr for pr in remaining_prs])}")
        else:
            print("\nNo PRs remaining in staging branch")

    def status(self) -> None:
        """Show status of staging branch."""
        if not self.is_initialized():
            print(f"Staging branch '{self.staging}' is not initialized")
            print("Run 'ghpr init' to initialize it")
            return

        base = self.get_base()
        prs = self.get_prs()

        print(f"Staging branch: {self.staging}")
        print(f"Base branch:    {base}")
        print(f"PRs staged:     {len(prs)}")

        if prs:
            print("\nStaged PRs:")
            for pr in prs:
                upstream = GitConfig.get(f"{self.config_prefix}.{pr}.upstream")
                upstream_branch = GitConfig.get(
                    f"{self.config_prefix}.{pr}.upstream-branch",
                )
                print(f"  PR #{pr}")
                if upstream:
                    print(f"    Upstream: {upstream}")
                if upstream_branch:
                    print(f"    Branch:   {upstream_branch}")


def main(argv: list[str] | None = None) -> None:
    """Eponymous main."""
    parser = argparse.ArgumentParser(
        description="GitHub Pull Request landing tool for FreeBSD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize staging branch
  ghpr init

  # Stage a PR for landing
  ghpr stage 1234

  # If rebase has conflicts, resolve them and continue
  git add <resolved-files>
  ghpr stage --continue 1234

  # Stage multiple PRs
  ghpr stage 1234
  ghpr stage 1235

  # Check status
  ghpr status

  # Remove a PR if you change your mind
  ghpr unstage 1234

  # Push all staged PRs to FreeBSD
  ghpr push
        """,
    )

    parser.add_argument(
        "--staging-branch",
        default="staging",
        help="Name of staging branch (default: %(default)s)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print all commands before executing them",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help=(
            "Show what would be done without actually doing it "
            "(automatically prints commands)"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Command to run",
        required=True,
    )

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize staging branch")
    init_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force re-initialization: delete existing staging branch and config",
    )

    # Stage command
    stage_parser = subparsers.add_parser("stage", help="Stage a PR for landing")
    stage_parser.add_argument("pr", type=int, help="PR number to stage")
    stage_parser.add_argument(
        "--reviewer",
        default=getpass.getuser(),
        help="Reviewer name for Reviewed-by trailer (default: %(default)s)",
    )
    stage_parser.add_argument(
        "--repo",
        default="freebsd-src",
        help="GitHub repository name (default: %(default)s)",
    )
    stage_parser.add_argument("--editor", help="Editor for commit message fixups")
    stage_parser.add_argument(
        "--continue",
        action="store_true",
        dest="do_continue",
        help="Continue an interrupted rebase",
    )
    stage_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force staging even if PR is already marked as staged",
    )

    # Push command
    push_parser = subparsers.add_parser("push", help="Push staged PRs to FreeBSD")
    push_parser.add_argument(
        "--push-pr-branches",
        action="store_true",
        help="Also push to PR branches (experimental)",
    )

    # Unstage command
    unstage_parser = subparsers.add_parser("unstage", help="Remove a staged PR")
    unstage_parser.add_argument("pr", type=int, help="PR number to unstage")

    # Status command
    subparsers.add_parser("status", help="Show staging branch status")

    args = parser.parse_args(args=argv)

    ghpr = GHPR(
        staging_branch=args.staging_branch,
        verbose=args.verbose,
        dry_run=args.dry_run,
    )

    if args.command == "init":
        ghpr.init(force=args.force)
    elif args.command == "stage":
        ghpr.stage(
            args.pr,
            reviewer=args.reviewer,
            repo=args.repo,
            editor=args.editor,
            do_continue=args.do_continue,
            force=args.force,
        )
    elif args.command == "push":
        ghpr.push(do_pr_branch_push=args.push_pr_branches)
    elif args.command == "unstage":
        ghpr.unstage(args.pr)
    elif args.command == "status":
        ghpr.status()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
