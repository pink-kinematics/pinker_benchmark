# SPDX-License-Identifier: Apache-2.0

"""Step one scenario, printing what each step records.

At each step, the two libraries build their problems from the same
configuration, as in the run function of the benchmark. This script will print
how far Pinker's problem was from Pink's, how far apart the two integrated to,
and the configuration reached, so that a rollout can be inspected, or a
mismatch traced to the step it appears at.

Steps wait for Enter, one keypress at a time. Call with ``--playback`` and a
playback speed ratio to let the scenario run on its own instead. You can also
to display the Pink configuration of the robot in MeshCat with ``--visualize``.
For example:

.. code:: console

    pixi run debug-scenario ur3 --visualize --playback 1
"""

import argparse
import time

import numpy as np
import qpsolvers
from pink_motions import SCENARIOS

from .scene import Scene
from .settings import DT, QP_SOLVER


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario",
        help="scenario to step, from the pink_motions library",
        choices=list(SCENARIOS.keys()),
    )
    parser.add_argument(
        "--qpsolver",
        help="backend quadratic programming solver",
        default=QP_SOLVER,
        choices=qpsolvers.available_solvers,
    )
    parser.add_argument(
        "--playback",
        type=float,
        default=None,
        metavar="SPEED",
        help="sleep this many timesteps between steps, rather than"
        " waiting for Enter",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="display the scene in MeshCat",
    )
    return parser.parse_args()


def main():
    """Step the scenario, printing what each step records."""
    args = parse_args()
    scenario = SCENARIOS[args.scenario]
    scene = Scene(scenario, visualize=args.visualize)
    for step, t in enumerate(np.arange(0.0, scenario.duration, DT)):
        record = scene.step(DT, solver=args.qpsolver)
        with np.printoptions(precision=4, suppress=True, linewidth=120):
            print(
                f"[{step}] t = {t:.3f} s,"
                f" QP distance = {record['qp_dist']:.1e},"
                " integration distance ="
                f" {record['integration_dist']:.1e},"
                f" q = {scene.configuration.q}"
            )
        if args.playback is None:
            input()
        else:  # playback speed specified
            time.sleep(args.playback * DT)


if __name__ == "__main__":
    main()
