# SPDX-License-Identifier: Apache-2.0

"""Tests for the statistics computed over the samples of a run."""

import math

import numpy as np
import pytest

from pinker_benchmark.stats import ConfidenceInterval, confidence_interval


class TestConfidenceInterval:
    """Tests for the interval the perf check reads."""

    def test_interval_is_symmetric_around_the_mean(self):
        """Bounds are the mean, plus or minus the half-width."""
        interval = ConfidenceInterval(mean=2.5, half_width=0.5)
        assert interval.low == pytest.approx(2.0)
        assert interval.high == pytest.approx(3.0)

    def test_mean_of_the_samples(self):
        """The interval is centred on the mean of the samples."""
        interval = confidence_interval(np.array([1.0, 2.0, 3.0, 4.0]))
        assert interval.mean == pytest.approx(2.5)

    def test_student_quantile(self):
        """The interval is Student's, which few samples call for.

        Four samples of variance 5/3 give a standard error of
        sqrt(5/3)/2, which t(0.975, 3) = 3.182 multiplies. The normal
        quantile would report an interval a third narrower.
        """
        interval = confidence_interval(np.array([1.0, 2.0, 3.0, 4.0]))
        standard_error = math.sqrt(5.0 / 3.0) / 2.0
        assert interval.half_width == pytest.approx(3.182446 * standard_error)

    def test_more_samples_narrow_the_interval(self):
        """Rolling out more times is what sharpens a run's conclusions."""
        samples = np.array([9.0, 10.0, 11.0])
        few = confidence_interval(samples)
        many = confidence_interval(np.tile(samples, 10))
        # Same mean and same dispersion, thirty samples instead of three
        assert many.mean == pytest.approx(few.mean)
        assert many.half_width < 0.25 * few.half_width

    @pytest.mark.parametrize("samples", [[], [42.0]])
    def test_too_few_samples_is_an_error(self, samples):
        """Fewer than two rollouts is a bug, not a figure to publish.

        A lone rollout says nothing about how it would have varied, and a
        proper run has ``NB_ROLLOUTS`` of them.
        """
        with pytest.raises(ValueError, match="not enough samples"):
            confidence_interval(np.array(samples))
