# SPDX-License-Identifier: Apache-2.0

"""Benchmark settings."""

# Simulation timestep, in seconds. Scenarios specify a duration rather
# than a number of steps, so this also decides how many steps a rollout
# times, and a run is only comparable with another one that used the same
# value. This timestep is therefore recorded in the results.
DT = 0.005

# QP solver both libraries hand their problems to. It is the same on both
# sides, so it cancels in the paired difference, but it decides how long a
# step takes and is therefore recorded in the results. We use Clarabel because
# some scenarios start outside their configuration limits, which makes their
# first QP infeasible for e.g. active-set solvers.
QP_SOLVER = "clarabel"

# CPU cores the benchmark pins itself to. The target hardware is a Raspberry Pi
# 4 Model B. The benchmark takes a single core by default, a decision mirrored
# from the software of Upkie wheeled bipeds where Pinker and Pink were used.
CPUS = (3,)

# Number of times each scenario is played out entirely. Metrics evaluated in
# this benchmark are computed across different rollouts with confidence
# intervals, so the number of rollouts should be at least two.
NB_ROLLOUTS = 10

# Confidence level of the intervals reported after ± symbols in reports.
CONFIDENCE_LEVEL = 0.95

# Performance of the two libraries is deemed the same when Pinker's step costs
# at most that much more than Pink's, in percent of Pink's mean step duration.
TIMINGS_TOLERANCE_PCT = 3.0

# Numerical tolerance for QP and configuration-space Chebyshev distances.
NUM_TOL = 1e-9
