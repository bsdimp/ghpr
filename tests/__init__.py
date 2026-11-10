"""Common test logic.

Copyright (c) 2026 Enji Cooper <ngie@FreeBSD.org>

SPDX-License-Identifier: BSD-2-Clause
"""

import os
from contextlib import contextmanager
from pathlib import Path

import git

os.environ["GIT_PYTHON_TRACE"] = "1"


@contextmanager
def sandbox(new_path: Path) -> None:
    """Contextmanager for changing directories temporarily in a test.

    Args:
        new_path: path to chdir to.

    """
    old_path = Path.cwd()
    os.chdir(new_path)
    try:
        yield
    finally:
        os.chdir(old_path)


def setup_freebsd_remote(
    repo_dir: Path, fetch_remote: str, push_remote: str | None = None,
) -> None:
    """Fixture that sets up a bogus repo with the https://."""
    repo = git.Repo(repo_dir)
    repo.create_remote("freebsd", fetch_remote)
    if fetch_remote is not None and fetch_remote != push_remote:
        freebsd_remote = repo.remotes.freebsd
        with freebsd_remote.config_writer as cw:
            cw.set("pushurl", push_remote or fetch_remote)


def format_result(result: ...) -> str:
    """Format results from `click.invoke(..)`."""
    return f"{result=} {result.output=}"
