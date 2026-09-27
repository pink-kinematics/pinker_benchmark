# SPDX-License-Identifier: Apache-2.0

"""Tests for the scene both libraries step together."""

import numpy as np
import pytest
import qpsolvers

from pinker_benchmark import SCENARIOS, Scene
from pinker_benchmark.results import (
    CHECK_COLUMNS,
    SAMPLE_COLUMNS,
    TIMING_COLUMNS,
)
from pinker_benchmark.settings import NUM_TOL

DT = 0.005  # seconds
SOLVER = "clarabel"


class TestScene:
    """Tests for how a scene holds and steps the two libraries."""

    def test_pink_side_is_the_scene(self):
        """Pink's side is the scene's own configuration and tasks."""
        scene = Scene(SCENARIOS["ur3"])
        side = scene.sides["pink"]
        assert side.configuration is scene.configuration
        assert side.tasks[0] is scene.trajectories[0].task

    def test_pinker_side_mirrors_the_scene(self):
        """Pinker's side is its own configuration, started from the same q."""
        scene = Scene(SCENARIOS["ur3"])
        side = scene.sides["pinker"]
        assert side.configuration is not scene.configuration
        assert np.array_equal(side.configuration.q, scene.q_init)
        assert len(side.tasks) == len(scene.tasks)

    def test_step_records_every_column(self):
        """A step records exactly what the results file stores."""
        scene = Scene(SCENARIOS["ur3"])
        record = scene.step(DT, SOLVER)
        assert set(record) == set(SAMPLE_COLUMNS)
        for column in TIMING_COLUMNS:
            assert isinstance(record[column], int)
            assert record[column] > 0
        for column in CHECK_COLUMNS:
            assert isinstance(record[column], float)
        assert scene.nb_steps == 1

    @pytest.mark.parametrize("name", ["ur3", "edo", "poppy_ergo_jr"])
    def test_libraries_agree_at_every_step(self, name):
        """Both libraries stay within tolerance of each other, step after step.

        This is the first criterion of the benchmark, as the run checks it:
        from the same configuration and the same targets, Pinker builds the
        same QP as Pink, and integrates the solution to the same place.
        """
        scene = Scene(SCENARIOS[name])
        for _ in range(100):
            record = scene.step(DT, SOLVER)
            assert record["qp_dist"] < NUM_TOL, name
            assert record["integration_dist"] < NUM_TOL, name

    def test_pinker_is_set_back_to_pink(self):
        """After a step, both sides hold the exact same configuration.

        This is what makes the next problems comparable: they are built
        from the same configuration, bit for bit, rather than from two
        that drifted apart by rounding.
        """
        scene = Scene(SCENARIOS["ur3"])
        for _ in range(5):
            scene.step(DT, SOLVER)
            assert np.array_equal(
                scene.sides["pinker"].configuration.q,
                scene.configuration.q,
            )

    def test_build_order_alternates(self, monkeypatch):
        """Pink goes first on even steps, Pinker on odd ones.

        Whatever the second call inherits from the first — cache warmth,
        branch predictor state — then falls on each library half of the
        time within every rollout.
        """
        scene = Scene(SCENARIOS["ur3"])
        calls = []
        for library, side in scene.sides.items():
            build_ik = side.adapter.build_ik

            def logged(*args, _library=library, _build=build_ik, **kwargs):
                calls.append(_library)
                return _build(*args, **kwargs)

            monkeypatch.setattr(side.adapter, "build_ik", logged)
        scene.step(DT, SOLVER)
        scene.step(DT, SOLVER)
        scene.step(DT, SOLVER)
        assert calls == ["pink", "pinker", "pinker", "pink", "pink", "pinker"]

    def test_solver_failure_is_an_error(self, monkeypatch):
        """A step the solver cannot take is reported, not integrated."""
        scene = Scene(SCENARIOS["ur3"])
        monkeypatch.setattr(
            qpsolvers,
            "solve_problem",
            lambda *args, **kwargs: qpsolvers.Solution(args[0]),
        )
        with pytest.raises(RuntimeError, match="no solution"):
            scene.step(DT, SOLVER)

    def test_reset(self):
        """A reset scene starts its scenario over."""
        scene = Scene(SCENARIOS["ur3"])
        for _ in range(5):
            scene.step(DT, SOLVER)
        assert not np.array_equal(scene.configuration.q, scene.q_init)
        scene.reset()
        assert scene.nb_steps == 0
        assert np.array_equal(scene.configuration.q, scene.q_init)
        for side in scene.sides.values():
            assert np.array_equal(side.configuration.q, scene.q_init)
        assert scene.sides["pink"].configuration is scene.configuration
