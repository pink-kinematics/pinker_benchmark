# SPDX-License-Identifier: Apache-2.0

"""Tests for the Pink and Pinker adapters."""

import pytest

from pinker_benchmark import SCENARIOS
from pinker_benchmark.adapters import get_adapter
from pinker_benchmark.metrics import problem_dist
from pinker_benchmark.scene import Scene
from pinker_benchmark.settings import NUM_TOL

DT = 0.005  # seconds


class TestGetAdapter:
    """Tests for how adapters are looked up."""

    def test_unknown_adapter(self):
        """An unknown library name raises a ValueError."""
        with pytest.raises(ValueError):
            get_adapter("nonsense")

    def test_adapters_are_named_after_their_library(self):
        """Each library compared has an adapter that answers to its name."""
        for library in ("pink", "pinker"):
            assert get_adapter(library).name == library

    def test_versions_name_the_library(self):
        """The version string of a library starts with its name."""
        for library in ("pink", "pinker"):
            assert get_adapter(library).version().startswith(library)


class TestMirroring:
    """Tests for how Pinker mirrors Pink."""

    @pytest.mark.parametrize("name", ["ur3", "jvrc", "edo", "poppy_ergo_jr"])
    def test_formulation_equivalence(self, name):
        """Pink and Pinker build the same QP from the same state.

        At the first step of a scenario, both sides of a fresh scene hold
        the same configuration and the same targets: the problems they
        build from it must coincide, coefficient by coefficient, to the
        tolerance of the benchmark.
        """
        scene = Scene(SCENARIOS[name])
        scene.step_targets(DT)
        scene.sync_targets()
        problems = {}
        for library, side in scene.sides.items():
            problems[library] = side.adapter.build_ik(
                side.configuration, side.tasks, DT, limits=side.limits
            )
        for field in ("P", "q", "G", "h"):
            assert getattr(problems["pinker"], field) is not None, name
        assert problem_dist(problems["pink"], problems["pinker"]) < NUM_TOL

    def test_mirrored_tasks_follow_their_specification(self):
        """Syncing targets copies the Pink target into the mirrored task."""
        scene = Scene(SCENARIOS["ur3"])
        for _ in range(10):
            scene.step_targets(DT)
        scene.sync_targets()
        side = scene.sides["pinker"]
        for mirrored_task, task in zip(side.tasks, scene.tasks):
            target = task.transform_target_to_world
            mirrored = mirrored_task.transform_target_to_world
            assert mirrored.translation == pytest.approx(target.translation)
            assert mirrored.rotation == pytest.approx(target.rotation)
