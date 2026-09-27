# SPDX-License-Identifier: Apache-2.0

"""Tests for the checks the benchmark concludes on."""

import math

import pytest

from pinker_benchmark import checks
from pinker_benchmark.checks import (
    FAIL_MARK,
    PASS_MARK,
    UNRESOLVED_MARK,
    ik_check_mark,
    perf_check_mark,
)
from pinker_benchmark.stats import ConfidenceInterval


class TestIKCheck:
    """Tests for the first check, on the QPs the two libraries build."""

    @pytest.fixture(autouse=True)
    def tolerance(self, monkeypatch):
        """Grant the two libraries 1e-9, whatever the settings say."""
        monkeypatch.setattr(checks, "NUM_TOL", 1e-9)

    def test_within_tolerance_passes(self):
        """Distances within tolerance are the same QP, integrated alike."""
        assert ik_check_mark(1e-12, 1e-12) == PASS_MARK
        assert ik_check_mark(1e-9, 1e-9) == PASS_MARK

    def test_beyond_tolerance_fails(self):
        """A distance beyond tolerance is another QP, however small."""
        assert ik_check_mark(2e-9, 1e-12) == FAIL_MARK
        assert ik_check_mark(math.inf, 1e-12) == FAIL_MARK

    def test_either_distance_fails_the_check(self):
        """Landing elsewhere fails the check as building another QP does.

        The two libraries are the same IK when they agree on both counts:
        the problem they build, and the configuration they integrate it to.
        """
        assert ik_check_mark(1e-12, 2e-9) == FAIL_MARK
        assert ik_check_mark(1e-12, math.inf) == FAIL_MARK


class TestPerfCheck:
    """Tests for the second check, on the step durations."""

    @pytest.fixture(autouse=True)
    def margin(self, monkeypatch):
        """Grant pinker 3% over pink, whatever the settings say.

        The margin is a setting rather than an argument, so a test that
        depends on its value patches it where the check reads it.
        """
        monkeypatch.setattr(checks, "TIMINGS_TOLERANCE_PCT", 3.0)

    @staticmethod
    def interval(low: float, high: float) -> ConfidenceInterval:
        """Relative interval with the given bounds."""
        mean = 0.5 * (low + high)
        return ConfidenceInterval(mean=mean, half_width=high - mean)

    def test_slower_beyond_the_margin_fails(self):
        """A whole interval above the margin is a failure.

        It says pinker costs more than the benchmark is willing to grant
        it over pink.
        """
        assert perf_check_mark(self.interval(0.05, 0.09)) == FAIL_MARK

    def test_within_the_margin_passes(self):
        """A whole interval inside the margin passes.

        This is the point of the margin: the two libraries are different
        programs, so they do differ, and what the benchmark checks is
        whether pinker costs more than it is willing to grant.
        """
        assert perf_check_mark(self.interval(-0.01, 0.02)) == PASS_MARK
        assert perf_check_mark(self.interval(0.005, 0.03)) == PASS_MARK

    def test_faster_than_the_margin_passes_too(self):
        """A library that is faster than the margin passes as well.

        The test is one-sided: pinker being cheaper than pink is not a
        regression, so it passes like equivalence does — and so does an
        interval spanning the two, which rules out being slower.
        """
        assert perf_check_mark(self.interval(-0.09, -0.05)) == PASS_MARK
        assert perf_check_mark(self.interval(-0.09, 0.01)) == PASS_MARK

    def test_straddling_the_margin_resolves_nothing(self):
        """An interval across the margin is a run too short to decide."""
        # Slower than the margin, or within it: this run cannot say.
        assert perf_check_mark(self.interval(0.01, 0.07)) == UNRESOLVED_MARK
        # Faster, slower or equivalent: even less so.
        assert perf_check_mark(self.interval(-0.4, 0.4)) == UNRESOLVED_MARK
