# SPDX-License-Identifier: Apache-2.0

"""Tests for the metrics used in the benchmark."""

import math

import numpy as np
import pytest
import qpsolvers

from pinker_benchmark.metrics import configuration_dist, problem_dist


def problem(**fields) -> qpsolvers.Problem:
    """A small QP, with the given fields overridden."""
    values = {
        "P": np.eye(2),
        "q": np.array([1.0, -1.0]),
        "G": np.array([[1.0, 0.0]]),
        "h": np.array([2.0]),
    }
    values.update(fields)
    return qpsolvers.Problem(**values)


class TestProblemDist:
    """Tests for the distance between two problems."""

    def test_same_problem(self):
        """Distance is zero on a copy."""
        assert problem_dist(problem(), problem()) == 0.0

    def test_largest_entry_wherever_it_is(self):
        """The distance is the largest difference between two entries."""
        P = np.eye(2)
        P[1, 0] = 3e-8
        assert problem_dist(problem(), problem(P=P)) == pytest.approx(3e-8)
        h = np.array([2.0 + 5e-8])
        assert problem_dist(problem(), problem(P=P, h=h)) == (
            pytest.approx(5e-8)
        )

    def test_fields_neither_has_do_not_count(self):
        """Removing constraints does not change the distance."""
        unconstrained = problem(G=None, h=None)
        assert problem_dist(unconstrained, problem(G=None, h=None)) == 0.0

    def test_missing_field_is_infinitely_off(self):
        """A constraint one side has and not the other is not the same QP."""
        without = problem(G=None, h=None)
        assert problem_dist(problem(), without) == math.inf
        assert problem_dist(without, problem()) == math.inf

    def test_different_shapes_are_infinitely_off(self):
        """More constraints on one side is not the same QP either."""
        taller = problem(G=np.eye(2), h=np.ones(2))
        assert problem_dist(problem(), taller) == math.inf

    def test_is_a_metric(self):
        """The distance is symmetric and satisfies the triangle inequality."""
        first = problem()
        second = problem(P=np.eye(2) + 1e-6, q=np.array([1.0, -1.0 + 2e-6]))
        third = problem(q=np.array([1.0 - 3e-6, -1.0]))
        assert problem_dist(first, second) == problem_dist(second, first)
        assert problem_dist(first, third) <= (
            problem_dist(first, second) + problem_dist(second, third)
        )


class TestConfigurationDist:
    """Tests for the distance between the two configurations."""

    def test_same_configuration(self):
        """A configuration is at zero distance from a copy of itself."""
        q = np.array([0.1, -0.2, 0.3])
        assert configuration_dist(q, q.copy()) == 0.0

    def test_largest_coordinate_wherever_it_is(self):
        """The distance is the largest difference between two coordinates."""
        q = np.array([0.1, -0.2, 0.3])
        other = q + np.array([1e-12, -4e-9, 2e-10])
        assert configuration_dist(q, other) == pytest.approx(4e-9)

    def test_is_a_metric(self):
        """The distance is symmetric and satisfies the triangle inequality."""
        q = np.array([0.1, -0.2, 0.3])
        r = q + np.array([1e-6, 0.0, -2e-6])
        s = q + np.array([0.0, 3e-6, 1e-6])
        assert configuration_dist(q, r) == configuration_dist(r, q)
        assert configuration_dist(q, s) <= (
            configuration_dist(q, r) + configuration_dist(r, s)
        )
