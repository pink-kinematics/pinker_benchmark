# SPDX-License-Identifier: Apache-2.0

"""Measurements from a benchmark."""

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

from .provenance import Provenance
from .stats import ConfidenceInterval, confidence_interval

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(HERE)
RESULTS_DIR = os.path.join(PROJECT_DIR, "results")

# Measurements are named after the commit they measured, so that runs of
# different versions accumulate rather than overwrite each other.
MEASUREMENTS_PATTERN = "{commit}.parquet"

# Measurements of a run made outside of the repository or of an unknown
# commit are not distinguished, so they may overwrite each other.
UNKNOWN_COMMIT = "unknown"

# Length of the commit hashes naming measurements.
SHORT_COMMIT = 9

# What the last run claimed, checksum of its measurements included:
# committed.
METADATA_PATH = os.path.join(RESULTS_DIR, "metadata.json")

# Where the results table is published.
README_PATH = os.path.join(PROJECT_DIR, "README.md")

# Key under which the run's metadata travels in the Parquet schema.
METADATA_KEY = b"comparison"

# Columns identifying a step.
INDEX_COLUMNS = ("scenario", "rollout", "step")

# What each phase of the step took, in nanoseconds.
TIMING_COLUMNS = (
    "pink_build_ns",
    "pinker_build_ns",
    "solve_ns",
    "pink_integrate_ns",
    "pinker_integrate_ns",
)

# How far apart the two libraries were at the step.
CHECK_COLUMNS = ("qp_dist", "integration_dist")

# Everything a step records, in the order of the columns of the file.
SAMPLE_COLUMNS = TIMING_COLUMNS + CHECK_COLUMNS


@dataclass
class ScenarioResult:
    """What a run measured on one scenario.

    Attributes:
        nv: Dimension of the robot's tangent space.
        nb_steps: Number of steps in a rollout of the scenario.
        samples: What each step recorded, one list per column of
            ``SAMPLE_COLUMNS``, rollout after rollout and step after step:
            timings in nanoseconds, distances in their own units.
    """

    nv: int
    nb_steps: int
    samples: Dict[str, List[float]]

    def samples_by_rollout(self, column: str) -> NDArray[np.float64]:
        """Samples of one column, one row per rollout.

        Args:
            column: Name of the column to read.

        Returns:
            Samples of the column, as a matrix with one row per rollout and
            one column per step of the scenario.
        """
        flat = np.asarray(self.samples[column], dtype=float)
        nb_rollouts = len(flat) // self.nb_steps
        return flat[: nb_rollouts * self.nb_steps].reshape(
            nb_rollouts, self.nb_steps
        )

    def raw_step_timings(self, library: str) -> NDArray[np.float64]:
        """Step durations of a library, in microseconds, one row per rollout.

        Args:
            library: Library whose steps to reconstruct, "pink" or "pinker".

        Returns:
            Step durations in microseconds, as a matrix with one row per
            rollout and one column per step of the scenario.
        """
        step_ns = sum(
            self.samples_by_rollout(column)  # (nb_rollouts, nb_steps)
            for column in (
                f"{library}_build_ns",
                "solve_ns",
                f"{library}_integrate_ns",
            )
        )
        return step_ns / 1e3

    def step_timings(self, library: str) -> ConfidenceInterval:
        """Mean step duration of a library, with its confidence interval.

        Args:
            library: Library whose steps to evaluate ("pink" or "pinker").

        Returns:
            Confidence interval of the average step duration of the library
            over this scenario, in microseconds.
        """
        timings = self.raw_step_timings(library)  # (nb_rollouts, nb_steps)
        rollout_mean_timings = timings.mean(axis=1)  # (nb_rollouts,)
        return confidence_interval(rollout_mean_timings)

    def max_dist(self, column: str) -> float:
        """Largest distance between the two libraries over the run.

        Args:
            column: Which distance: between the problems the two libraries
                built (``qp_dist``), or between the configurations they
                integrated to (``integration_dist``).

        Returns:
            Largest value of that distance, over every step of every
            rollout.
        """
        assert column in ["qp_dist", "integration_dist"]
        return float(np.max(self.samples[column]))

    def step_relative_diff(self) -> ConfidenceInterval:
        """Relative difference in step timings between Pinker and Pink.

        Average Pink step timings are used as the normalizing constant.

        Returns:
            Relative difference with its confidence interval. Positive means
            Pinker is slower.
        """
        raw_difference = self.raw_step_timings(
            "pinker"
        ) - self.raw_step_timings("pink")
        difference = confidence_interval(raw_difference.mean(axis=1))
        pink_us = self.step_timings("pink").mean
        return ConfidenceInterval(
            mean=difference.mean / pink_us,
            half_width=difference.half_width / pink_us,
        )


@dataclass
class Results:
    """What a benchmark run measured, and the conditions it measured it in.

    Attributes:
        date: Day of the run, as ``YYYY-MM-DD``.
        machine: Architecture of the machine, as ``platform.machine()``
            names it: ``aarch64`` on the Raspberry Pi the benchmark
            targets.
        dt: Timestep of every rollout, in seconds.
        qpsolver: QP solver Pink's problems were handed to.
        rollouts: Number of rollouts of each scenario, the sample size
            behind every statistic of the run.
        cpus: Cores the run pinned itself to, comma-separated; empty when
            it ran unpinned.
        provenance: Commit the run measured and the state of the working
            tree; None when the run was made outside of a git repository.
        versions: Version of everything that decides what was measured,
            by name: ``pink``, ``pinker`` and ``robot_descriptions``.
        scenarios: What was measured on each scenario, by name.
    """

    date: str
    machine: str
    dt: float
    qpsolver: str
    rollouts: int
    cpus: str
    provenance: Optional[Provenance]
    versions: Dict[str, str]
    scenarios: Dict[str, ScenarioResult]

    @property
    def metadata(self) -> dict:
        """Everything about the run but its samples, as plain JSON."""
        provenance = self.provenance
        return {
            "date": self.date,
            "machine": self.machine,
            "dt": self.dt,
            "qpsolver": self.qpsolver,
            "rollouts": self.rollouts,
            "cpus": self.cpus,
            "provenance": (
                asdict(provenance) if provenance is not None else None
            ),
            "versions": dict(self.versions),
            "scenarios": {
                name: {"nv": scenario.nv, "steps": scenario.nb_steps}
                for name, scenario in self.scenarios.items()
            },
        }

    def to_table(self) -> pa.Table:
        """Lay the samples out as a table, carrying the metadata.

        Returns:
            Table of the samples, one row per step per rollout, with the
            rest of the run in its schema metadata.
        """
        columns: Dict[str, list] = {
            name: [] for name in INDEX_COLUMNS + SAMPLE_COLUMNS
        }
        for name, scenario in self.scenarios.items():
            nb_samples = len(scenario.samples[SAMPLE_COLUMNS[0]])
            nb_rollouts = nb_samples // scenario.nb_steps
            columns["scenario"] += [name] * nb_samples
            # Samples are recorded rollout after rollout.
            columns["rollout"] += list(
                np.repeat(
                    np.arange(nb_rollouts, dtype=np.int16), scenario.nb_steps
                )
            )
            columns["step"] += list(
                np.tile(
                    np.arange(scenario.nb_steps, dtype=np.int32),
                    nb_rollouts,
                )
            )
            for column in SAMPLE_COLUMNS:
                columns[column] += list(scenario.samples[column])

        table = pa.table(
            {
                "scenario": pa.array(columns["scenario"]).dictionary_encode(),
                "rollout": pa.array(columns["rollout"], type=pa.int16()),
                "step": pa.array(columns["step"], type=pa.int32()),
            }
            | {
                column: pa.array(columns[column], type=pa.int64())
                for column in TIMING_COLUMNS
            }
            | {
                column: pa.array(columns[column], type=pa.float64())
                for column in CHECK_COLUMNS
            }
        )
        return table.replace_schema_metadata(
            {METADATA_KEY: json.dumps(self.metadata).encode("utf-8")}
        )

    @classmethod
    def from_table(cls, table: pa.Table) -> "Results":
        """Rebuild the results of a run from a table of its samples.

        Args:
            table: Table of samples, with the run's metadata attached.

        Returns:
            Results of the run.
        """
        metadata = json.loads(
            table.schema.metadata[METADATA_KEY].decode("utf-8")
        )
        scenarios = np.asarray(table.column("scenario").to_pylist())
        rollouts = table.column("rollout").to_numpy()
        steps = table.column("step").to_numpy()
        samples = {
            column: table.column(column).to_numpy()
            for column in SAMPLE_COLUMNS
        }
        results = {}
        for name, entry in metadata["scenarios"].items():
            rows = np.flatnonzero(scenarios == name)
            # Rows are written rollout after rollout, and read back in the
            # same order, but sort to be independent of the writer.
            rows = rows[np.lexsort((steps[rows], rollouts[rows]))]
            results[name] = ScenarioResult(
                nv=entry["nv"],
                nb_steps=entry["steps"],
                samples={
                    column: samples[column][rows].tolist()
                    for column in SAMPLE_COLUMNS
                },
            )
        provenance = metadata["provenance"]
        return cls(
            date=metadata["date"],
            machine=metadata["machine"],
            dt=metadata["dt"],
            qpsolver=metadata["qpsolver"],
            rollouts=metadata["rollouts"],
            cpus=metadata["cpus"],
            provenance=(
                Provenance(**provenance) if provenance is not None else None
            ),
            versions=metadata["versions"],
            scenarios=results,
        )

    def write(
        self, path: str, metadata_path: Optional[str] = METADATA_PATH
    ) -> None:
        """Write the measurements of the run.

        Args:
            path: Path to write to.
            metadata_path: Path to write the run's metadata to, checksum
                of the measurements included.
        """
        table = self.to_table()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        # Timings are noisy: stored as such they barely compress, but their
        # deltas do. Distances are floats with noisy mantissas, whose sign
        # and exponent bytes at least compress once split off.
        column_encoding = {
            column: "DELTA_BINARY_PACKED" for column in TIMING_COLUMNS
        } | {column: "BYTE_STREAM_SPLIT" for column in CHECK_COLUMNS}
        pq.write_table(
            table,
            path,
            compression="zstd",
            compression_level=19,
            column_encoding=column_encoding,
            use_dictionary=["scenario"],
        )
        print(f"Wrote {path}")
        if metadata_path is None:
            return
        metadata = self.metadata
        metadata["measurements"] = {
            "path": os.path.basename(path),
            "sha256": checksum(path),
            "bytes": os.path.getsize(path),
            "rows": table.num_rows,
        }
        os.makedirs(os.path.dirname(metadata_path) or ".", exist_ok=True)
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"Wrote {metadata_path}")

    @classmethod
    def read(cls, path: str) -> "Results":
        """Read results from a past run of the benchmark.

        Args:
            path: Path to the measurements of the run.

        Returns:
            Results of the run.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{path} not found. Measurements are not committed: run the"
                " benchmark to produce them. What the last run claimed, if"
                f" any, is in {os.path.basename(METADATA_PATH)}."
            )
        return cls.from_table(pq.read_table(path))


def measurements_path(provenance: Optional[Provenance] = None) -> str:
    """Path to the measurements of a run.

    Measurements are named after the commit they measured. Runs of the same
    commit do overwrite each other, deliberately: they measure the same
    software.

    Args:
        provenance: Provenance of the run, None outside of a repository.

    Returns:
        Path to write the measurements of the run to.
    """
    commit = UNKNOWN_COMMIT
    if provenance is not None:
        commit = provenance.commit[:SHORT_COMMIT]
    return os.path.join(
        RESULTS_DIR, MEASUREMENTS_PATTERN.format(commit=commit)
    )


def last_measurements_path(
    metadata_path: str = METADATA_PATH,
) -> Optional[str]:
    """Path to the measurements of the last run, as its metadata has it.

    Args:
        metadata_path: Path to the metadata of the last run.

    Returns:
        Path to the measurements the last run wrote, None if no run is
        on record.
    """
    metadata = read_metadata(metadata_path)
    if metadata is None or "measurements" not in metadata:
        return None
    return os.path.join(
        os.path.dirname(metadata_path), metadata["measurements"]["path"]
    )


def checksum(path: str) -> str:
    """SHA-256 of a file, as a hexadecimal string.

    Args:
        path: Path to the file.

    Returns:
        Checksum of the file.
    """
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_metadata(metadata_path: str = METADATA_PATH) -> Optional[dict]:
    """Read what the last committed run claimed, if it is recorded.

    Args:
        metadata_path: Path to the run's metadata.

    Returns:
        Metadata of the run, None if it is not recorded.
    """
    if not os.path.exists(metadata_path):
        return None
    with open(metadata_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def check_measurements(
    path: str, metadata_path: str = METADATA_PATH
) -> Optional[bool]:
    """Check measurements against the checksum their metadata recorded.

    Args:
        path: Path to the measurements.
        metadata_path: Path to the metadata recorded next to them.

    Returns:
        Whether the measurements are the ones the metadata was written
        for, or None if there is nothing to check them against: no metadata
        on record, or no measurements lying around. The latter is the state
        of a fresh checkout, where ``Results.read`` is the one that reports
        it.
    """
    metadata = read_metadata(metadata_path)
    if metadata is None or "measurements" not in metadata:
        return None
    if not os.path.exists(path):
        return None
    return checksum(path) == metadata["measurements"]["sha256"]
