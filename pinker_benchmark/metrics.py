# SPDX-License-Identifier: Apache-2.0

"""Metrics used to compare quadratic programs and configurations.

Both are Chebyshev distances, that is, the largest absolute difference between
coordinates. This norm was selected because it does not grow with the dimension
of the problem: a 7-DoF and a 6-DoF arm are held to the same tolerance on their
respective joint angles, and the same holds for humanoids on both floating-base
and joint-angle coordinates.
"""

import math

import numpy as np
import qpsolvers
from numpy.typing import NDArray

PROBLEM_FIELDS = ("P", "q", "G", "h", "A", "b", "lb", "ub")


def problem_dist(
    pink_problem: qpsolvers.Problem, pinker_problem: qpsolvers.Problem
) -> float:
    """Chebyshev distance between the coefficients of two quadratic programs.

    Args:
        pink_problem: Problem built by Pink.
        pinker_problem: Problem built by Pinker.

    Returns:
        Largest absolute difference between two corresponding coefficients
        of the two problems, over every field. The distance is infinite if a
        field is only in one of them, or if its shapes differ.
    """
    dist = 0.0
    for field in PROBLEM_FIELDS:
        pink_value = getattr(pink_problem, field)
        pinker_value = getattr(pinker_problem, field)
        if pink_value is None and pinker_value is None:
            continue
        if pink_value is None or pinker_value is None:
            return math.inf
        pink_value = np.asarray(pink_value)
        pinker_value = np.asarray(pinker_value)
        if pink_value.shape != pinker_value.shape:
            return math.inf
        dist = max(dist, float(np.max(np.abs(pink_value - pinker_value))))
    return dist


def configuration_dist(
    pink_q: NDArray[float], pinker_q: NDArray[float]
) -> float:
    """Chebyshev distance between two configuration vectors.

    Both libraries lay the configuration out the same way, so the vectors
    compare coordinate by coordinate: radians for revolute joints, meters
    and unit-quaternion coordinates for a floating base.

    Args:
        pink_q: Configuration vector of Pink.
        pinker_q: Configuration vector of Pinker.

    Returns:
        Largest absolute difference between two corresponding coordinates.
    """
    return float(np.max(np.abs(pink_q - pinker_q)))
