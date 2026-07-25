"""Git subroutines/interfaces."""

import os
import typing
from collections.abc import Sequence

import git
from git.cmd import Git

if typing.TYPE_CHECKING:
    from typing import Self


class GitHelper:
    """git command wrapper."""

    def __init__(
        self: "Self",
        *,
        dry_run: bool = False,
        verbose: bool = False,
        working_dir: ... = None,
    ) -> None:
        self._dry_run = dry_run
        self._git = Git(working_dir=working_dir)
        if verbose:
            os.environ["GIT_PYTHON_TRACE"] = "full"

    def run(
        self: "Self",
        git_args: str | Sequence[...],
        *args: Sequence[...],
        check: bool = True,
        capture: bool = False,
        safe: bool = False,
        **kwargs: dict,
    ) -> str | tuple[int, str, str]:
        """Execute commands."""
        if self._dry_run and not safe:
            return (0, "", "")

        kwargs["stdout_as_string"] = True
        kwargs["with_exceptions"] = check
        # Git.execute(... with_extended_output=False, ...) crashes with versions of the
        # library: https://github.com/gitpython-developers/GitPython/pull/2126 .
        # kwargs["with_stdout"] = capture
        kwargs["with_stdout"] = True
        kwargs.setdefault("with_extended_output", True)

        if isinstance(git_args, str):
            git_cmd = f"{Git.GIT_PYTHON_GIT_EXECUTABLE} {git_args}"
        else:
            git_cmd = [Git.GIT_PYTHON_GIT_EXECUTABLE, *git_args]
        return self._git.execute(git_cmd, *args, **kwargs)

    def rev_parse(self: "Self", git_args: list, *args: list, **kwargs: dict) -> ...:
        """Proxy for `git rev-parse`."""
        kwargs["safe"] = True
        return self.run(["rev-parse", *git_args], *args, **kwargs)

    def branch_exists(self: "Self", branch: str) -> bool:
        """Check if a branch exists.

        Args:
            branch: branch to test for.

        Returns:
            True if it exists; False if it does not exist.

        """
        returncode, _, _ = self.rev_parse(["--verify", branch], check=False)
        return returncode == 0

    def checkout(
        self: "Self",
        branch: str,
        create: bool = False,
        base: str | None = None,
    ) -> None:
        """Checkout a branch, optionally creating it."""
        git_args = ["checkout"]
        if create:
            git_args.extend(["-b", branch])
            if base is not None:
                git_args.append(base)
        else:
            git_args.append(branch)
        self.run(git_args)

    def config(
        self: "Self",
        git_args: list,
        *args: list,
        **kwargs: dict,
    ) -> ...:
        """Proxy for `git config`."""
        return self.run(["config", *git_args], *args, **kwargs)

    def rebase(
        self: "Self",
        base: str,
        *args: list,
        onto: str | None = None,
        interactive: bool = False,
        exec_cmd: str | None = None,
        **kwargs: dict,
    ) -> None:
        """Rebase current branch."""
        git_args = []
        if interactive:
            git_args.append("-i")
        if onto:
            git_args.extend(["--onto", onto])
        if exec_cmd:
            git_args.extend(["--exec", exec_cmd])
        git_args.append(base)
        self.run(["rebase", *git_args], *args, **kwargs)

    def push(
        self: "Self",
        remote: str,
        refspec: str,
        force: bool = False,
        push_option: str | None = None,
    ) -> bool:
        """Push to remote, return True if successful."""
        git_args = []
        if push_option:
            git_args.extend(["--push-option", push_option])
        if force:
            git_args.append("--force")
        git_args.extend([remote, refspec])
        returncode, _, _ = self.run(["push", *git_args], check=False)
        return returncode == 0

    def fetch(self: "Self", remote: str, *args: list, **kwargs: dict) -> None:
        """Fetch from remote."""
        kwargs["safe"] = True
        self.run(["fetch", remote], *args, **kwargs)

    def pull(self: "Self", rebase: bool = True, *args: list, **kwargs: dict) -> None:
        """Pull from current upstream."""
        self.run(["pull", "--rebase"] if rebase else [], *args, **kwargs)

    def branch(self: "Self", git_args: list, *args: list, **kwargs: dict) -> None:
        """Proxy for `git branch`."""
        self.run(["branch", *git_args], *args, **kwargs)

    def delete_branch(
        self: "Self",
        branch: str,
        force: bool = True,
        *args: list,
        **kwargs: dict,
    ) -> None:
        """Delete a branch."""
        self.branch(["-D" if force else "-d", branch], *args, **kwargs)

    def move_branch(self: "Self", branch: str, target: str = "HEAD") -> None:
        """Force-move a branch to a specific commit and check it out."""
        # Force-move the branch pointer
        self.branch(["-f", branch, target])
        # Check out the branch
        self.checkout([branch])

    def get_commits_with_trailer(
        self: "Self",
        base: str,
        head: str,
        trailer: str,
        value: str,
    ) -> list[str]:
        """Get commit hashes that contain a specific trailer value.

        Args:
            base: base reference.
            head: HEAD reference.
            trailer: the prefix to search for.
            value: the suffix to search for.

        Returns:
            All commit hashes that contain the specific "needle" between
            `{base}...{head}`.

        """
        cmd = [
            "--format=%H",
            "--grep",
            f"^{trailer}: .*{value}",
            f"{base}..{head}",
        ]
        output = self.log(
            cmd,
            strip_newline_in_stdout=True,
            with_extended_output=False,
        )
        return [
            line.strip() for line in output.splitlines(keepends=False) if line.strip()
        ]

    def cherry_pick(
        self: "Self",
        git_args: list[str],
        *args: list,
        **kwargs: dict,
    ) -> None:
        """Cherry-pick commits."""
        self.run(["cherry-pick", *git_args], *args, **kwargs)

    def log(self: "Self", git_args: list, *args: list, **kwargs: dict) -> ...:
        """Proxy for `git log`."""
        kwargs.setdefault("capture", True)
        kwargs["safe"] = True
        return self.run(["log", *git_args], *args, **kwargs)

    def remote(self: "Self", git_args: list, *args: list, **kwargs: dict) -> ...:
        """Proxy for `git remote`."""
        kwargs.setdefault("safe", True)
        return self.run(["remote", *git_args], *args, **kwargs)


class GitConfig(GitHelper):
    """Helper class for git config operations."""

    def get(self: "Self", key: str, default: str | None = None) -> str | None:
        """Get a git config value."""
        try:
            output = self.config(
                ["--get", key],
                safe=True,
                strip_newline_in_stdout=True,
                with_extended_output=False,
                with_stdout=True,
            )
        except git.exc.GitCommandError:
            return default
        else:
            return output

    def get_all(self: "Self", key: str) -> list[str]:
        """Get all values for a git config key."""
        output = self.config(
            ["--get-all", key],
            check=False,  # The section might not exist.
            safe=True,
            strip_newline_in_stdout=True,
            with_extended_output=False,
            with_stdout=True,
        )
        return [
            line.strip() for line in output.splitlines(keepends=False) if line.strip()
        ]

    def set(
        self: "Self",
        key: str,
        value: ...,
        config_type: str | None = None,
        add: bool = False,
    ) -> None:
        """Sets/appends `value` to the `git config` denoted by `key`.

        Args:
            key: config key.
            value: value to set in the git config.
            config_type: a specific type to treat `value` as. See `git config --type`
                         for more details.
            add: Append `value` to any preexisting configuration denoted by
                 `key` if True and set `value` verbatim to `key` if False.

        """
        args = []
        if config_type:
            args.extend(["--type", config_type])
        if add:
            args.append("--add")
        args.extend([key, str(value)])
        self.config(args)

    def unset(
        self: "Self",
        key: str,
        value: str | None = None,
    ) -> None:
        """Unset a git config value."""
        args = ["--unset", key]
        if value:
            args.append(value)
        self.config(args, check=False)

    def remove_section(
        self: "Self",
        section: str,
    ) -> None:
        """Remove a git config section."""
        self.config(["--remove-section", section])
