# SPDX-License-Identifier: Apache-2.0

"""Tests for the git provenance of a benchmark run."""

import os
import subprocess

import pytest

from pinker_benchmark.provenance import collect_provenance


def git(repository, *args) -> None:
    """Run a git command in a repository."""
    subprocess.run(
        ["git", "-C", str(repository), *args], check=True, capture_output=True
    )


def write(path, contents: str = "x") -> None:
    """Write a file, creating its directory if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(contents)


@pytest.fixture
def repository(tmp_path):
    """A repository with one commit, the benchmark project at its root."""
    git(tmp_path, "init", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "bench@example.com")
    git(tmp_path, "config", "user.name", "Bench")
    write(str(tmp_path / "benchmark.py"), "print('hello')\n")
    git(tmp_path, "add", "benchmark.py")
    git(tmp_path, "commit", "-m", "Initial commit")
    return tmp_path


class TestProvenance:
    """Tests for the provenance of a run."""

    def test_clean_repository(self, repository):
        """A clean working tree has a commit and no change."""
        provenance = collect_provenance(str(repository))
        assert len(provenance.commit) == 40
        assert provenance.changes == []

    def test_modified_file_is_a_change(self, repository):
        """Editing a tracked file makes the run unreproducible."""
        write(str(repository / "benchmark.py"), "print('edited')\n")
        provenance = collect_provenance(str(repository))
        assert provenance.changes == ["benchmark.py"]

    def test_untracked_file_is_a_change(self, repository):
        """An uncommitted module is as unreproducible as an edit."""
        write(str(repository / "new_module.py"))
        provenance = collect_provenance(str(repository))
        assert provenance.changes == ["new_module.py"]

    def test_first_status_line_is_parsed_whole(self, repository):
        """The leading blank of a status code is not eaten.

        Regression test: stripping the output of git status dropped the
        first character of the first path, turning `.gitignore` into
        `gitignore`.
        """
        write(str(repository / ".dotfile"), "first in status order\n")
        git(repository, "add", ".dotfile")
        git(repository, "commit", "-m", "Add a dotfile")
        write(str(repository / ".dotfile"), "edited\n")
        write(str(repository / "zzz.py"))
        provenance = collect_provenance(str(repository))
        assert provenance.changes == [".dotfile", "zzz.py"]

    def test_results_are_not_a_change(self, repository):
        """The benchmark's own output doesn't make the tree dirty.

        A run rewrites its measurements, their metadata and the README table:
        left in the dirty check, they would block the next run.
        """
        write(str(repository / "results" / "0ff1ce123.parquet"))
        write(str(repository / "results" / "metadata.json"))
        write(str(repository / "README.md"))
        provenance = collect_provenance(str(repository))
        assert provenance.changes == []

    def test_results_are_excluded_from_a_subdirectory(self, tmp_path):
        """Results are excluded wherever the project sits in the repo.

        The exclusions are git pathspecs, relative to the directory git
        runs in, so they hold whether the benchmark is a repository of its
        own or a subdirectory of a larger one. A change elsewhere in that
        larger repository still counts: it is code the run measured.
        """
        git(tmp_path, "init", "--initial-branch=main")
        git(tmp_path, "config", "user.email", "bench@example.com")
        git(tmp_path, "config", "user.name", "Bench")
        project_dir = str(tmp_path / "pinker_benchmark")
        write(os.path.join(project_dir, "benchmark.py"), "print('hi')\n")
        write(os.path.join(str(tmp_path), "elsewhere.py"), "print('hi')\n")
        git(tmp_path, "add", ".")
        git(tmp_path, "commit", "-m", "Initial commit")

        write(os.path.join(project_dir, "results", "0ff1ce123.parquet"))
        write(os.path.join(project_dir, "README.md"), "# results\n")
        assert collect_provenance(project_dir).changes == []
        write(os.path.join(str(tmp_path), "elsewhere.py"), "print('bye')\n")
        assert collect_provenance(project_dir).changes == ["elsewhere.py"]

    def test_outside_a_repository(self, tmp_path):
        """An installed copy of the bench has no provenance to record."""
        assert collect_provenance(str(tmp_path)) is None
