# SPDX-License-Identifier: Apache-2.0

"""Tests for reading and writing results."""

import json
import os

import pyarrow.parquet as pq
import pytest

from pinker_benchmark.provenance import Provenance
from pinker_benchmark.results import (
    CHECK_COLUMNS,
    INDEX_COLUMNS,
    SAMPLE_COLUMNS,
    TIMING_COLUMNS,
    Results,
    ScenarioResult,
    check_measurements,
    checksum,
    last_measurements_path,
    measurements_path,
    read_metadata,
)

NB_STEPS = 5
NB_ROLLOUTS = 3


def make_results() -> Results:
    """Results of a run, with made-up samples."""
    nb_samples = NB_ROLLOUTS * NB_STEPS
    samples = {
        # Distinct values per column, and enough of them for NB_ROLLOUTS
        # rollouts of NB_STEPS steps each.
        column: [1000 * (index + 1) + offset for index in range(nb_samples)]
        for offset, column in enumerate(TIMING_COLUMNS)
    } | {
        column: [
            1e-12 * (index + 1) * (offset + 1) for index in range(nb_samples)
        ]
        for offset, column in enumerate(CHECK_COLUMNS)
    }
    return Results(
        date="2026-07-14",
        machine="x86_64",
        dt=0.005,
        qpsolver="clarabel",
        rollouts=NB_ROLLOUTS,
        cpus="",
        provenance=Provenance(commit="0" * 40, changes=[]),
        versions={"pink": "pink 4.2.0", "pinker": "pinker 0.1.0"},
        scenarios={
            "ur3": ScenarioResult(nv=6, nb_steps=NB_STEPS, samples=samples),
        },
    )


@pytest.fixture
def written(tmp_path):
    """Write a run to a temporary directory."""
    report_path = str(tmp_path / "0ff1ce123.parquet")
    metadata_path = str(tmp_path / "metadata.json")
    make_results().write(report_path, metadata_path)
    return report_path, metadata_path


class TestMeasurementsPath:
    """Tests for how the measurements of a run are named."""

    def test_named_after_the_commit(self):
        """Runs of different commits do not overwrite each other."""
        first = measurements_path(Provenance(commit="a" * 40, changes=[]))
        second = measurements_path(Provenance(commit="b" * 40, changes=[]))
        assert os.path.basename(first) == "aaaaaaaaa.parquet"
        assert first != second

    def test_outside_a_repository(self):
        """A run with no commit to name its measurements after still runs."""
        path = measurements_path(None)
        assert os.path.basename(path) == "unknown.parquet"

    def test_same_commit_overwrites(self):
        """Re-running the same software overwrites its own measurements."""
        provenance = Provenance(commit="c" * 40, changes=[])
        assert measurements_path(provenance) == measurements_path(provenance)

    def test_last_run_is_found_through_its_metadata(self, written):
        """The report finds the measurements the last run wrote."""
        report_path, metadata_path = written
        found = last_measurements_path(metadata_path)
        assert os.path.basename(found) == os.path.basename(report_path)

    def test_no_run_on_record(self, tmp_path):
        """No run on record is not a crash."""
        assert last_measurements_path(str(tmp_path / "absent.json")) is None


class TestResults:
    """Tests for the results of a comparison run."""

    def test_samples_round_trip(self, written):
        """Samples read back exactly as they were written, column by column."""
        report_path, _ = written
        ur3 = Results.read(report_path).scenarios["ur3"]
        expected = make_results().scenarios["ur3"]
        for column in SAMPLE_COLUMNS:
            assert ur3.samples[column] == expected.samples[column]

    def test_one_row_per_step(self, written):
        """The file is one row per step per rollout, both libraries in it."""
        report_path, _ = written
        table = pq.read_table(report_path)
        assert table.num_rows == NB_ROLLOUTS * NB_STEPS
        assert set(table.column_names) == set(INDEX_COLUMNS + SAMPLE_COLUMNS)
        assert "library" not in table.column_names
        # Rows are written rollout after rollout, step after step
        rollouts = table.column("rollout").to_pylist()
        steps = table.column("step").to_pylist()
        assert rollouts[: NB_STEPS + 1] == [0] * NB_STEPS + [1]
        assert steps[:NB_STEPS] == list(range(NB_STEPS))

    def test_metadata_round_trip(self, written):
        """Everything but the samples survives the round trip."""
        report_path, _ = written
        results = Results.read(report_path)
        expected = make_results()
        assert results.metadata == expected.metadata
        assert results.provenance == Provenance("0" * 40, [])
        assert results.scenarios["ur3"].nv == 6
        assert results.scenarios["ur3"].nb_steps == NB_STEPS

    def test_metadata_is_written_next_to_the_measurements(self, written):
        """The run's claims are recorded in plain text, checksum included."""
        report_path, metadata_path = written
        metadata = read_metadata(metadata_path)
        assert metadata["measurements"]["path"] == "0ff1ce123.parquet"
        assert metadata["measurements"]["sha256"] == checksum(report_path)
        assert metadata["measurements"]["bytes"] == os.path.getsize(
            report_path
        )
        assert metadata["measurements"]["rows"] == NB_ROLLOUTS * NB_STEPS
        # Samples themselves stay out of the committed metadata
        assert "samples" not in json.dumps(metadata)

    def test_check_measurements_accepts_what_it_recorded(self, written):
        """Untouched measurements match the checksum recorded for them."""
        report_path, metadata_path = written
        assert check_measurements(report_path, metadata_path) is True

    def test_check_measurements_detects_tampering(self, written):
        """Measurements that did not produce the metadata are caught."""
        report_path, metadata_path = written
        with open(report_path, "ab") as handle:
            handle.write(b"\x00")
        assert check_measurements(report_path, metadata_path) is False

    def test_check_measurements_without_metadata(self, written, tmp_path):
        """Nothing to check the measurements against is not a failure."""
        report_path, _ = written
        absent = str(tmp_path / "elsewhere.json")
        assert check_measurements(report_path, absent) is None

    def test_check_measurements_without_measurements(self, written):
        """A fresh checkout has the metadata but not the measurements.

        Regression test: the checksum was computed before the file was
        known to exist, so the report crashed where it meant to explain
        that the measurements have to be benchmarked again.
        """
        report_path, metadata_path = written
        os.remove(report_path)
        assert check_measurements(report_path, metadata_path) is None

    def test_read_without_measurements(self, tmp_path):
        """Measurements are not committed: their absence is explained."""
        absent = str(tmp_path / "comparison.parquet")
        with pytest.raises(FileNotFoundError, match="not committed"):
            Results.read(absent)
