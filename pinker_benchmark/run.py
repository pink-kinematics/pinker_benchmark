# SPDX-License-Identifier: Apache-2.0

"""Benchmark Pinker against Pink over the bench scenarios."""

import argparse
import datetime
import os
import platform
import sys
import time
from typing import Dict, List, Optional

import numpy as np
import robot_descriptions
from pink_motions import SCENARIOS

from .adapters import get_adapter
from .provenance import Provenance, collect_provenance
from .report import publish_results
from .results import (
    METADATA_PATH,
    SAMPLE_COLUMNS,
    Results,
    ScenarioResult,
    measurements_path,
)
from .scene import Scene
from .settings import CPUS, DT, NB_ROLLOUTS, QP_SOLVER


def benchmark_scenario(name: str, samples: Dict[str, List]) -> dict:
    """Roll out one scenario once, recording what every step measures.

    Args:
        name: Name of the scenario, from the bench library.
        samples: Step records to append to, one list per column of
            ``results.SAMPLE_COLUMNS``.

    Returns:
        Dictionary with scenario metadata and the final configuration.
    """
    scenario = SCENARIOS[name]
    scene = Scene(scenario, visualize=False)
    nb_steps = len(np.arange(0.0, scenario.duration, DT))
    for _ in range(nb_steps):
        record = scene.step(DT, solver=QP_SOLVER)
        for column in SAMPLE_COLUMNS:
            samples[column].append(record[column])
    return {
        "scenario": name,
        "nq": scene.configuration.model.nq,
        "nv": scene.configuration.model.nv,
        "steps": nb_steps,
        "q_final": [float(x) for x in scene.configuration.q],
    }


def check_provenance(allow_dirty: bool) -> Optional[Provenance]:
    """Commit under benchmark, refusing to run a dirty working tree.

    Args:
        allow_dirty: If set, report uncommitted changes rather than
            exiting on them.

    Returns:
        Provenance of the run, None outside of a git repository.
    """
    provenance = collect_provenance()
    if provenance is None or not provenance.dirty:
        return provenance
    changes = provenance.changes
    print(f"{len(changes)} uncommitted change(s) in the repository:")
    for path in changes:
        print(f"    {path}")
    if not allow_dirty:
        print(
            "\nRefusing to benchmark uncommitted changes: their results"
            " could not be reproduced.\nCommit them, or re-run with"
            " --allow-dirty to record the run as dirty anyway."
        )
        sys.exit(1)
    print("\nBenchmarking a dirty working tree: results are not reproducible")
    return provenance


def pin_to_cpus() -> str:
    """Pin this process to the CPU cores the benchmark runs on.

    Returns:
        Cores the process was pinned to, comma-separated, empty if it was
        not pinned at all.
    """
    if not CPUS or not hasattr(os, "sched_setaffinity"):
        return ""
    if (os.cpu_count() or 1) <= max(CPUS):
        print(
            f"Not pinning: this machine has {os.cpu_count()} core(s),"
            f" too few to spare CPU(s) {CPUS}. Timings will be noisier."
        )
        return ""
    os.sched_setaffinity(0, set(CPUS))
    return ",".join(str(cpu) for cpu in CPUS)


def format_duration(seconds: float) -> str:
    """Spell out a duration in hours, minutes and seconds.

    Args:
        seconds: Duration to format, in seconds.

    Returns:
        Duration as ``H h M min S s``, rounded down to the second.
    """
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours} h {minutes} min {seconds} s"


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="benchmark uncommitted changes (results won't be reproducible)",
    )
    return parser.parse_args()


def main():
    """Run the benchmark and write its resulting report."""
    start_time = time.perf_counter()
    args = parse_args()
    provenance = check_provenance(args.allow_dirty)
    cpus = pin_to_cpus()

    samples = {
        name: {column: [] for column in SAMPLE_COLUMNS} for name in SCENARIOS
    }
    metadata = {}
    for rollout in range(NB_ROLLOUTS):
        for name in SCENARIOS:
            print(f"[rollout {rollout + 1}/{NB_ROLLOUTS}] {name}...")
            metadata[name] = benchmark_scenario(name, samples[name])

    results = Results(
        date=str(datetime.date.today()),
        machine=platform.machine(),
        dt=DT,
        qpsolver=QP_SOLVER,
        rollouts=NB_ROLLOUTS,
        cpus=cpus,
        provenance=provenance,
        versions={
            library: get_adapter(library).version()
            for library in ("pink", "pinker")
        }
        | {
            "robot_descriptions": (
                f"robot_descriptions {robot_descriptions.__version__}"
            )
        },
        scenarios={
            name: ScenarioResult(
                nv=metadata[name]["nv"],
                nb_steps=metadata[name]["steps"],
                samples=samples[name],
            )
            for name in SCENARIOS
        },
    )

    meas_path = measurements_path(provenance)  # named after current commit
    results.write(meas_path, METADATA_PATH)
    publish_results(meas_path)

    nb_steps = sum(len(samples[name][SAMPLE_COLUMNS[0]]) for name in SCENARIOS)
    duration = format_duration(time.perf_counter() - start_time)
    print(f"\nBenchmark completed: ran {nb_steps} steps in {duration}")


if __name__ == "__main__":
    main()
