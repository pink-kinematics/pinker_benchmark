# SPDX-License-Identifier: Apache-2.0

"""Statistics computed over the samples of a run."""

from dataclasses import dataclass

import numpy as np
import scipy.stats
from numpy.typing import NDArray

from .settings import CONFIDENCE_LEVEL


@dataclass(frozen=True)
class ConfidenceInterval:
    """Mean and half-width of the estimate's confidence interval.

    Attributes:
        mean: Mean of the samples.
        half_width: Half-width of the ``CONFIDENCE_LEVEL`` interval of that
            mean.
    """

    mean: float
    half_width: float

    @property
    def low(self) -> float:
        """Lower bound of the interval."""
        return self.mean - self.half_width

    @property
    def high(self) -> float:
        """Upper bound of the interval."""
        return self.mean + self.half_width


def confidence_interval(
    samples: NDArray[np.float64],
) -> ConfidenceInterval:
    """Mean of a set of samples, with its confidence interval.

    Args:
        samples: Samples to average.

    Returns:
        Mean of the samples, with the half-width of the ``CONFIDENCE_LEVEL``
        interval of that mean from Student's t-distribution.

    Raises:
        ValueError: If there are fewer than two samples, which say nothing
            about their own dispersion. A proper run has ``NB_ROLLOUTS`` of
            them.
    """
    if len(samples) < 2:
        raise ValueError("not enough samples to compute a confidence interval")
    mean = float(np.mean(samples))
    quantile = float(
        scipy.stats.t.ppf(0.5 + 0.5 * CONFIDENCE_LEVEL, len(samples) - 1)
    )
    half_width = quantile * float(scipy.stats.sem(samples))
    return ConfidenceInterval(mean=mean, half_width=half_width)
