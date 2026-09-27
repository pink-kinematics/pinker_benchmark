# SPDX-License-Identifier: Apache-2.0

"""Checks the benchmark concludes on."""

from .settings import NUM_TOL, TIMINGS_TOLERANCE_PCT
from .stats import ConfidenceInterval

PASS_MARK = "✅"
FAIL_MARK = "❌"
UNRESOLVED_MARK = "❔"


def ik_check_mark(qp_dist: float, integration_dist: float) -> str:
    """Conclude on whether Pinker produces the same differential IK as Pink.

    Args:
        qp_dist: Largest distance between two QPs built by the libraries over
            all rollouts of the scenario.
        integration_dist: Largest distance between two post-integration
            configurations over all rollouts of the scenario.

    Returns:
        Mark of the check: pass if that distance is within tolerance, fail
        otherwise.
    """
    return (
        PASS_MARK
        if qp_dist <= NUM_TOL and integration_dist <= NUM_TOL
        else FAIL_MARK
    )


def perf_check_mark(step_relative_diff: ConfidenceInterval) -> str:
    """Conclude on whether Pinker is not slower than Pink.

    Args:
        step_relative_diff: Confidence interval of the step-time difference,
            relative to Pink's mean step duration.

    Returns:
        Mark of the check: pass if the whole interval lies at or below the
        margin, fail if it lies wholly above, unresolved if it straddles
        the margin.
    """
    margin = TIMINGS_TOLERANCE_PCT / 100.0
    if step_relative_diff.high <= margin:
        return PASS_MARK
    if step_relative_diff.low > margin:
        return FAIL_MARK
    return UNRESOLVED_MARK
