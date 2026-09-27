# SPDX-License-Identifier: Apache-2.0

"""Scenario rolled out by the benchmark."""

import copy
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import meshcat_shapes
import pink
import pinocchio as pin
import qpsolvers
from pink.tasks import FrameTask
from pink.utils import custom_configuration_vector
from pink.visualization import start_meshcat_visualizer
from pink_motions import Scenario
from robot_descriptions.loaders.pinocchio import load_robot_description

from .adapters import Adapter, get_adapter
from .metrics import configuration_dist, problem_dist


@dataclass
class Side:
    """One side of the comparison: a library's own view of the scenario.

    Attributes:
        adapter: Adapter to the target IK library (Pink or Pinker).
        configuration: The library's configuration of the robot.
        tasks: The library's tasks, mirrored from the scenario's Pink ones.
        limits: The library's limits, ``None`` to fall back to its defaults.
    """

    adapter: Adapter
    configuration: object
    tasks: List
    limits: Optional[List]


class Scene:
    """A bench scenario rolled out by the benchmark.

    A scene loads the robot of a scenario, deep-copies its trajectories and
    holds the state the rollout advances: the Pink configuration, and one
    side per library compared, holding that library's own configuration,
    tasks and limits.

    Scenarios are specified with Pink tasks, and Pink drives the rollout. At
    every step, both libraries build the IK problem from the same
    configuration, Pink's problem is solved once, and both integrate the
    solution. Pinker's problem is compared with Pink's, and so are the
    configurations the two libraries integrate to. At the next step, Pinker
    will be set back to Pink's configuration in order to start from the exact
    same problem again. Mirrored tasks are created once, and their targets
    synced at every step (see ``sync_targets``), so that both libraries see the
    same target sequence by construction.

    The optional MeshCat visualizer can display the Pink configuration. We use
    it in the debug script.

    Attributes:
        configuration: Pink configuration of the robot.
        nb_steps: Number of steps taken since the start of the scenario.
        q_init: Initial configuration vector of the scenario.
        robot: Pinocchio robot wrapper, loaded from the robot description.
        scenario: Scenario this scene instantiates.
        sides: Configuration, tasks and limits of each library, by name.
            Pink's side shares ``configuration`` and the tasks of the
            trajectories; Pinker's side mirrors them.
        trajectories: Task targets moved by ``step_targets``.
        viewer: MeshCat viewer, ``None`` unless visualizing.
        visualizer: MeshCat visualizer, ``None`` unless visualizing.
    """

    configuration: pink.Configuration
    nb_steps: int
    robot: pin.RobotWrapper
    sides: Dict[str, Side]

    def __init__(self, scenario: Scenario, visualize: bool = False):
        """Create a new scene.

        Args:
            scenario: Scene description.
            visualize: If set, visualize scenario in MeshCat.

        Raises:
            ValueError: if the scenario is empty.
            IndexError: if the initial configuration does not match the robot
                model.
        """
        robot = load_robot_description(
            description_name=scenario.robot_description,
            root_joint=scenario.root_joint,
        )

        # Deep-copy trajectories: scenario objects are shared singletons,
        # and trajectories (with their Pink tasks) are stateful.
        trajectories = copy.deepcopy(scenario.trajectories)

        visualizer = None
        viewer = None
        if visualize:
            visualizer = start_meshcat_visualizer(robot)
            viewer = visualizer.viewer
            viewer["/Background"].set_property("top_color", [1] * 3)
            viewer["/Background"].set_property("bottom_color", [1] * 3)
            viewer["/Grid"].set_property("visible", False)
            viewer["/Cameras/default/rotated/<object>"].set_property(
                "zoom", 2.0
            )

        if len(trajectories) < 1:
            robot_frames = [
                frame.name
                for frame in robot.model.frames
                if frame.name != "universe"
            ]
            raise ValueError(
                "Scenario is empty, maybe add a task for one of:\n\n- "
                + ("\n- ".join(robot_frames))
            )

        try:
            q_init = custom_configuration_vector(
                robot, **scenario.initial_configuration
            )
        except IndexError as exn:
            queried_joints = list(scenario.initial_configuration.keys())
            valid_joints = list(robot.model.names)
            raise IndexError(
                f"One joint in {queried_joints} not found, "
                f"names must be in {valid_joints}"
            ) from exn

        if visualize:
            visualizer.display(q_init)
        configuration = pink.Configuration(robot.model, robot.data, q_init)
        for trajectory in trajectories:
            trajectory.reset(configuration, viewer)
            task = trajectory.task
            if viewer is not None and hasattr(task, "frame"):
                frame = task.frame
                meshcat_shapes.frame(viewer[f"{frame}_current"], opacity=1.0)
                meshcat_shapes.frame(viewer[f"{frame}_target"], opacity=0.5)

        self.configuration = configuration
        self.nb_steps = 0
        self.q_init = q_init
        self.robot = robot
        self.scenario = scenario
        self.trajectories = trajectories
        self.viewer = viewer
        self.visualizer = visualizer
        self.sides = {
            library: self._make_side(library) for library in ("pink", "pinker")
        }

    def _make_side(self, library: str) -> Side:
        """Instantiate the scenario in one library.

        Pink gets the scene's own configuration and the tasks of its
        trajectories. Pinker loads its own robot and mirrors those tasks.

        Args:
            library: Name of the library.

        Returns:
            The library's side of the comparison.
        """
        adapter = get_adapter(library)
        if library == "pink":
            configuration = self.configuration
            tasks = self.tasks
        else:  # library == "pinker"
            robot = adapter.load_robot(self.scenario)
            configuration = adapter.make_configuration(robot, self.q_init)
            tasks = [adapter.mirror_task(task) for task in self.tasks]
        limits = adapter.make_limits(configuration, self.scenario)
        return Side(adapter, configuration, tasks, limits)

    def reset(self):
        """Reset the scene to the start of its scenario."""
        model = self.robot.model
        data = self.robot.data
        if self.visualizer is not None:
            self.visualizer.display(self.q_init)
        self.configuration = pink.Configuration(model, data, self.q_init)
        for trajectory in self.trajectories:
            trajectory.reset(self.configuration, self.viewer)
        self.sides = {
            library: self._make_side(library) for library in ("pink", "pinker")
        }
        self.nb_steps = 0

    def sync_targets(self) -> None:
        """Update mirrored task targets from their Pink specifications."""
        for side in self.sides.values():
            for mirrored_task, task in zip(side.tasks, self.tasks):
                side.adapter.sync_target(mirrored_task, task)

    @property
    def tasks(self) -> List[pink.Task]:
        """Pink tasks of the scene, one per trajectory."""
        return [trajectory.task for trajectory in self.trajectories]

    @property
    def frame_tasks(self) -> List[FrameTask]:
        """Frame tasks of the scene, a subset of ``tasks``."""
        return [
            trajectory.task
            for trajectory in self.trajectories
            if isinstance(trajectory.task, FrameTask)
        ]

    def step_targets(self, dt: float) -> None:
        """Advance targets for a given duration.

        Args:
            dt: Duration in seconds.
        """
        for trajectory in self.trajectories:
            trajectory.step(dt)

        if self.viewer is None:
            return
        for task in self.frame_tasks:
            if not hasattr(task, "frame"):
                continue
            frame = task.frame
            target = task.transform_target_to_world
            current = self.configuration.get_transform_frame_to_world(frame)
            self.viewer[f"{frame}_target"].set_transform(target.np)
            self.viewer[f"{frame}_current"].set_transform(current.np)

    def step(self, dt: float, solver: str) -> Dict[str, float]:
        """Advance the scene and save measurements for each library.

        Both libraries build the differential IK problem from the same
        configuration. Pink's problem is solved once, and the resulting
        velocity is integrated by both libraries for distance measurements. The
        order of the two builds, and of the two integrations, alternates from
        one step to the next, so that whatever advantage the second call could
        inherit from the first (cache warmth, branch predictor state, ...) is
        shared equally and cancels out over the rollout.

        Args:
            dt: Duration in seconds.
            solver: Backend quadratic programming (QP) solver.

        Returns:
            Measurements (timings and numerical distances) made during the
            step.

        Raises:
            RuntimeError: if the solver finds no solution.
        """
        self.step_targets(dt)
        self.sync_targets()
        if self.nb_steps % 2 == 0:
            order = ("pink", "pinker")
        else:
            order = ("pinker", "pink")
        record = {}
        problems = {}
        for library in order:
            side = self.sides[library]
            start_ns = time.perf_counter_ns()
            problems[library] = side.adapter.build_ik(
                side.configuration, side.tasks, dt, limits=side.limits
            )
            record[f"{library}_build_ns"] = time.perf_counter_ns() - start_ns

        start_ns = time.perf_counter_ns()
        result = qpsolvers.solve_problem(problems["pink"], solver=solver)
        if result.x is None:
            raise RuntimeError(
                f"{solver} found no solution at step {self.nb_steps}"
            )
        velocity = result.x / dt
        record["solve_ns"] = time.perf_counter_ns() - start_ns

        for library in order:
            configuration = self.sides[library].configuration
            start_ns = time.perf_counter_ns()
            configuration.integrate_inplace(velocity, dt)
            record[f"{library}_integrate_ns"] = (
                time.perf_counter_ns() - start_ns
            )

        pinker_configuration = self.sides["pinker"].configuration
        record["qp_dist"] = problem_dist(problems["pink"], problems["pinker"])
        record["integration_dist"] = configuration_dist(
            self.configuration.q, pinker_configuration.q
        )
        pinker_configuration.update(self.configuration.q)
        if self.visualizer is not None:
            self.visualizer.display(self.configuration.q)
        self.nb_steps += 1
        return record
