# SPDX-License-Identifier: Apache-2.0

"""Adapters to treat Pink and Pinker with a unified interface."""

import abc
from typing import List, Optional

import numpy as np
import pink
import pinker
import pinocchio as pin
from pink_motions import Scenario
from pinker import kinematics
from robot_descriptions.loaders.pinocchio import load_robot_description


def _make_limits(
    model,
    scenario: Scenario,
    configuration_limit,
    velocity_limit_cls,
    floating_base_limit=None,
) -> Optional[List]:
    """Assemble a scenario's velocity limit for a given model.

    Args:
        model: Robot model of the library the limits are built for.
        scenario: Scenario whose velocity limits are applied.
        configuration_limit: The library's default configuration limit.
        velocity_limit_cls: The library's ``VelocityLimit`` class.
        floating_base_limit: The library's floating-base velocity limit, if
            applicable.

    Returns:
        The list of limits, or ``None`` when the scenario does not specify a
        custom velocity limit (in that case, defaults will apply).
    """
    if scenario.velocity_limit is None:
        return None
    v_max = scenario.velocity_limit * np.ones(model.nv)
    limits = [
        configuration_limit,
        velocity_limit_cls(model, velocity_limit=v_max),
    ]
    if floating_base_limit is not None:
        limits.append(floating_base_limit)
    return limits


class Adapter(abc.ABC):
    """Wrapper around a differential IK library."""

    name: str

    @abc.abstractmethod
    def version(self) -> str:
        """Version string of the library and its kinematics backend."""

    @abc.abstractmethod
    def load_robot(self, scenario: Scenario):
        """Load the scenario's robot description with the library."""

    @abc.abstractmethod
    def make_configuration(self, robot, q_init):
        """Create a configuration for the library."""

    @abc.abstractmethod
    def mirror_task(self, task: pink.Task):
        """Mirror a Pink task specification into this library."""

    @abc.abstractmethod
    def sync_target(self, mirrored_task, task: pink.Task) -> None:
        """Update a mirrored task's target from its Pink specification."""

    @abc.abstractmethod
    def make_limits(self, configuration, scenario: Scenario) -> Optional[list]:
        """Mirror a scenario's limits into this library's own model."""

    @abc.abstractmethod
    def build_ik(self, configuration, tasks, dt: float, limits=None):
        """Build the differential IK problem as a qpsolvers.Problem."""


class PinkAdapter(Adapter):
    """Pink is the reference implementation we validate Pinker against."""

    name = "pink"

    def version(self) -> str:
        """Version string of the library and its kinematics backend."""
        return f"pink {pink.__version__} (pinocchio {pin.__version__})"

    def load_robot(self, scenario: Scenario):
        """Load the scenario's robot description."""
        return load_robot_description(
            description_name=scenario.robot_description,
            root_joint=scenario.root_joint,
        )

    def make_configuration(self, robot, q_init):
        """Create the configuration rolled out by Pink."""
        return pink.Configuration(robot.model, robot.data, q_init)

    def mirror_task(self, task: pink.Task):
        """Pink tasks are the specification: mirroring is the identity."""
        return task

    def sync_target(self, mirrored_task, task: pink.Task) -> None:
        """Nothing to sync: the mirrored task is the specification."""

    def make_limits(self, configuration, scenario: Scenario) -> Optional[list]:
        """Build the scenario's limits with Pink's own limit classes."""
        model = configuration.model
        return _make_limits(
            model,
            scenario,
            model.configuration_limit,
            pink.limits.VelocityLimit,
            getattr(model, "floating_base_velocity_limit", None),
        )

    def build_ik(self, configuration, tasks, dt: float, limits=None):
        """Build the differential IK problem, as a qpsolvers.Problem."""
        return pink.build_ik(configuration, tasks, dt, limits=limits)


class PinkerAdapter(Adapter):
    """Pinker, whose kinematics backend ships inside the library."""

    name = "pinker"

    def version(self) -> str:
        """Version string of the library.

        The kinematics backend is ``pinker.kinematics``, a subpackage, so
        the library version covers it.
        """
        return f"pinker {pinker.__version__}"

    def convert_root_joint(self, root_joint: Optional[pin.JointModel]):
        """Name root joint model the way Pinker expects it."""
        if root_joint is None:
            return None
        shortname = root_joint.shortname()
        root_joint_names = {
            "JointModelFreeFlyer": "free_flyer",
            "JointModelPlanar": "planar",
        }
        if shortname in root_joint_names:
            return root_joint_names[shortname]
        raise NotImplementedError(
            f"root joint {shortname} not supported by the Pinker adapter"
        )

    def load_robot(self, scenario: Scenario):
        """Load the scenario's robot description."""
        return pinker.load_robot_description(
            description_name=scenario.robot_description,
            root_joint=self.convert_root_joint(scenario.root_joint),
        )

    def make_configuration(self, robot, q_init):
        """Create the configuration rolled out by Pinker."""
        return pinker.Configuration(robot.model, robot.data, q_init)

    def mirror_task(self, task: pink.Task):
        """Mirror a Pink task specification into Pinker."""
        if isinstance(task, pink.tasks.FrameTask):
            return pinker.tasks.FrameTask(
                task.frame,
                position_cost=task.cost[0:3].copy(),
                orientation_cost=task.cost[3:6].copy(),
                lm_damping=task.lm_damping,
                gain=task.gain,
            )
        raise NotImplementedError(
            f"mirroring {type(task).__name__} into pinker "
            "is not implemented yet"
        )

    def sync_target(self, mirrored_task, task: pink.Task) -> None:
        """Update a mirrored task's target from its Pink specification."""
        target = task.transform_target_to_world
        mirrored_task.set_target(
            kinematics.SE3(target.rotation, target.translation)
        )

    def make_limits(self, configuration, scenario: Scenario) -> Optional[list]:
        """Build the scenario's limits with Pinker's own limit classes.

        Pinker carries a configuration's default limits on the
        configuration itself, as ``default_limits``: the ones the scenario
        keeps are picked from there by class.
        """

        def default_limit(limit_cls):
            for limit in configuration.default_limits:
                if isinstance(limit, limit_cls):
                    return limit
            return None

        return _make_limits(
            configuration.model,
            scenario,
            default_limit(pinker.limits.ConfigurationLimit),
            pinker.limits.VelocityLimit,
            default_limit(pinker.limits.FloatingBaseVelocityLimit),
        )

    def build_ik(self, configuration, tasks, dt: float, limits=None):
        """Build the differential IK problem as a qpsolvers.Problem."""
        return pinker.build_ik(configuration, tasks, dt, limits=limits)


def get_adapter(name: str) -> Adapter:
    """Get the adapter of an IK library from its name.

    Args:
        name: Name of the IK library, "pink" or "pinker".

    Returns:
        Adapter over that library.

    Raises:
        ValueError: if the name is not one of the two libraries compared.
    """
    if name == "pink":
        return PinkAdapter()
    if name == "pinker":
        return PinkerAdapter()
    raise ValueError(f"unknown IK library: {name!r}")
