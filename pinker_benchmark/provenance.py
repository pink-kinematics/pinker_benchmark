# SPDX-License-Identifier: Apache-2.0

"""Git provenance of a benchmark run.

Measurements are only comparable when they all come from the same code. We
record the commit the benchmark ran at, and refuse to run on a dirty
working tree unless explicitly requested to.
"""

import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))

PROJECT_DIR = os.path.dirname(HERE)

# Files the benchmark writes to are excluded from the dirty check: a run
# would otherwise leave the tree dirty and block the next one.
IGNORED_PATHSPECS = (":(exclude)results", ":(exclude)README.md")


@dataclass
class Provenance:
    """Commit and working-tree status of the repository.

    Attributes:
        commit: Hash of the current commit when the run started.
        changes: Paths that differed from that commit, sorted, excluding the
            files that the benchmark writes to. Empty for a clean tree.
    """

    commit: str
    changes: List[str]

    @property
    def dirty(self) -> bool:
        """Whether the working tree had changes from the commit."""
        return bool(self.changes)


def _git(repository: str, *args: str) -> Optional[str]:
    """Run a git command in a repository, or None if it fails.

    Only trailing newlines are stripped: the leading space of a porcelain
    status line is part of the status code.
    """
    try:
        return subprocess.run(
            ["git", "-C", repository, *args],
            capture_output=True,
            check=True,
            text=True,
        ).stdout.rstrip("\n")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def collect_provenance(
    project_dir: str = PROJECT_DIR,
) -> Optional[Provenance]:
    """Commit and working-tree status of the repository under benchmark.

    Args:
        project_dir: Directory of the benchmark project.

    Returns:
        The current commit and the files that differ from it, or None if
        the project is not in a git repository (for instance, an
        installed copy of the bench).
    """
    commit = _git(project_dir, "rev-parse", "HEAD")
    if commit is None:  # not a git repository
        return None
    # Untracked files count, ignored files don't
    status = _git(
        project_dir, "status", "--porcelain", "--", *IGNORED_PATHSPECS
    )
    changes: List[str] = [line[3:] for line in (status or "").splitlines()]
    return Provenance(commit=commit, changes=sorted(changes))
