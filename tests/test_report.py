# SPDX-License-Identifier: Apache-2.0

"""Tests for the Markdown report of a comparison run."""

from typing import List, Optional

import numpy as np
import pytest
import wcwidth

from pinker_benchmark import checks, report
from pinker_benchmark.checks import FAIL_MARK, PASS_MARK, UNRESOLVED_MARK
from pinker_benchmark.report import Report
from pinker_benchmark.results import Results, ScenarioResult
from pinker_benchmark.stats import confidence_interval

NB_STEPS = 4
NB_ROLLOUTS = 3

# Every mark a scenario can be given, which the table lays out alike.
MARKS = (PASS_MARK, FAIL_MARK, UNRESOLVED_MARK)

# What the shared solve and each library's integration take on every step
# of the results below, in µs. The rest of a step is its build.
SOLVE_US = 1000.0
PINK_INTEGRATE_US = 100.0
PINKER_INTEGRATE_US = 140.0


def set_num_tol(monkeypatch, num_tol: float) -> None:
    """Move the numerical tolerance everywhere the report reads it.

    The tolerance decides the IK check, where the check reads it, and the
    figures the report states around it, where the report does.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        num_tol: Tolerance to grant the two libraries.
    """
    monkeypatch.setattr(checks, "NUM_TOL", num_tol)
    monkeypatch.setattr(report, "NUM_TOL", num_tol)


def set_timings_tolerance_pct(monkeypatch, tolerance_pct: float) -> None:
    """Move the timings margin everywhere the report reads it.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tolerance_pct: Margin to grant pinker over pink, in percent.
    """
    monkeypatch.setattr(checks, "TIMINGS_TOLERANCE_PCT", tolerance_pct)
    monkeypatch.setattr(report, "TIMINGS_TOLERANCE_PCT", tolerance_pct)


def scenario_result(
    pink_timings: List[List[float]],
    pinker_timings: List[List[float]],
    qp_dist: float = 1e-12,
    integration_dist: Optional[float] = None,
    nv: int = 6,
) -> ScenarioResult:
    """Results of one scenario, from the step durations of each library.

    Args:
        pink_timings: Pink step durations, per rollout and per step, in µs.
        pinker_timings: Pinker step durations, per rollout and per step, in µs.
        qp_dist: Distance between the two problems, on every step.
        integration_dist: Distance between the two integrated
            configurations, on every step; the QP one by default.
        nv: Dimension of the tangent space.

    Returns:
        Results of the scenario.
    """
    if integration_dist is None:
        integration_dist = qp_dist
    nb_samples = NB_ROLLOUTS * NB_STEPS

    def get_build_ns(steps_us, non_build_us: float) -> List[int]:
        return [
            int(1e3 * (step_us - non_build_us))
            for rollout in steps_us
            for step_us in rollout
        ]

    return ScenarioResult(
        nv=nv,
        nb_steps=NB_STEPS,
        samples={
            "pink_build_ns": get_build_ns(
                pink_timings, SOLVE_US + PINK_INTEGRATE_US
            ),
            "pinker_build_ns": get_build_ns(
                pinker_timings, SOLVE_US + PINKER_INTEGRATE_US
            ),
            "solve_ns": [int(1e3 * SOLVE_US)] * nb_samples,
            "pink_integrate_ns": [int(1e3 * PINK_INTEGRATE_US)] * nb_samples,
            "pinker_integrate_ns": [int(1e3 * PINKER_INTEGRATE_US)]
            * nb_samples,
            "qp_dist": [qp_dist] * nb_samples,
            "integration_dist": [integration_dist] * nb_samples,
        },
    )


@pytest.fixture
def flat_results():
    """Pink 50 µs slower on every step, and no outlier: a flat run."""
    return scenario_result(
        pink_timings=[[1300] * NB_STEPS] * NB_ROLLOUTS,
        pinker_timings=[[1250] * NB_STEPS] * NB_ROLLOUTS,
    )


@pytest.fixture
def spiked_results():
    """Pink 50 µs slower on every step, and one of its steps an outlier."""
    return scenario_result(
        pink_timings=[
            [1300, 1300, 1300, 1300],
            [1300, 1300, 9300, 1300],
            [1300] * NB_STEPS,
        ],
        pinker_timings=[[1250] * NB_STEPS] * NB_ROLLOUTS,
    )


class TestStepTimings:
    """Tests for the step durations the report reconstructs."""

    def test_one_row_per_rollout(self, spiked_results):
        """Timings are laid out rollout by rollout, step by step."""
        timings = spiked_results.raw_step_timings("pink")
        assert timings.shape == (NB_ROLLOUTS, NB_STEPS)
        assert timings[1, 2] == pytest.approx(9300.0)  # the outlier

    def test_step_is_build_plus_solve_plus_integrate(self, flat_results):
        """A library's step is its own build and integration, plus the solve.

        Timings are stored in nanoseconds, per phase, and reported in
        microseconds, per step. The two integrations take different times,
        so a step summed with the other library's would not add up.
        """
        samples = flat_results.samples
        for library in ("pink", "pinker"):
            expected_us = (
                np.asarray(samples[f"{library}_build_ns"])
                + np.asarray(samples["solve_ns"])
                + np.asarray(samples[f"{library}_integrate_ns"])
            ) / 1e3
            assert np.allclose(
                flat_results.raw_step_timings(library).ravel(), expected_us
            )
        assert np.allclose(flat_results.raw_step_timings("pink"), 1300.0)
        assert np.allclose(flat_results.raw_step_timings("pinker"), 1250.0)

    def test_integration_is_per_library(self, flat_results):
        """Each library's step counts its own integration, not the other's."""
        nb_samples = NB_ROLLOUTS * NB_STEPS
        flat_results.samples["pinker_integrate_ns"] = [
            int(1e3 * (PINKER_INTEGRATE_US + 70.0))
        ] * nb_samples
        assert np.allclose(flat_results.raw_step_timings("pink"), 1300.0)
        assert np.allclose(flat_results.raw_step_timings("pinker"), 1320.0)

    def test_solve_is_counted_in_both(self, flat_results):
        """The shared solve is part of what either library's step costs."""
        flat_results.samples["solve_ns"] = [0] * (NB_ROLLOUTS * NB_STEPS)
        assert np.allclose(
            flat_results.raw_step_timings("pink"), 1300.0 - SOLVE_US
        )
        assert np.allclose(
            flat_results.raw_step_timings("pinker"), 1250.0 - SOLVE_US
        )

    def test_solve_cancels_in_the_difference(self, flat_results):
        """The shared solve is the same number on both sides: it cancels.

        Whatever it takes, what separates the two libraries is their
        builds and their integrations, which is what the paired
        difference of their step durations is left with.
        """
        before = flat_results.raw_step_timings(
            "pinker"
        ) - flat_results.raw_step_timings("pink")
        flat_results.samples["solve_ns"] = [
            int(1e6 * (index % 7)) for index in range(NB_ROLLOUTS * NB_STEPS)
        ]
        after = flat_results.raw_step_timings(
            "pinker"
        ) - flat_results.raw_step_timings("pink")
        assert np.allclose(after, before)

    def test_step_timings_average_over_rollouts(self, spiked_results):
        """Each rollout is one sample of a library's step duration.

        pink's three rollouts average 1300, 3300 and 1300 µs — the second one
        carries the 9300 µs outlier — so the mean step is 1967 µs,
        with an interval wide enough to say that the run cannot tell what
        a step costs. pinker's rollouts all agree, hence a zero width.
        """
        pink = spiked_results.step_timings("pink")
        assert pink.mean == pytest.approx((1300.0 + 3300.0 + 1300.0) / 3)
        assert pink.half_width > 2000.0
        pinker = spiked_results.step_timings("pinker")
        assert pinker.mean == pytest.approx(1250.0)
        assert pinker.half_width == pytest.approx(0.0)


class TestMaxDist:
    """Tests for the distance the report retains of a run."""

    def test_largest_over_the_run(self, flat_results):
        """One bad step anywhere in the run is what the report retains."""
        flat_results.samples["qp_dist"][7] = 2e-7
        assert flat_results.max_dist("qp_dist") == pytest.approx(2e-7)
        assert flat_results.max_dist("integration_dist") == (
            pytest.approx(1e-12)
        )


class TestStepRelativeDifference:
    """Tests for the difference between the two libraries."""

    def test_sign_convention(self, flat_results):
        """Negative means pinker is faster than pink."""
        faster = flat_results.step_relative_diff()
        # 1250 against 1300, relative to a 1300 µs step
        assert faster.mean == pytest.approx(-50.0 / 1300.0)
        slower = scenario_result(
            [[1250] * NB_STEPS] * NB_ROLLOUTS,
            [[1300] * NB_STEPS] * NB_ROLLOUTS,
        ).step_relative_diff()
        assert slower.mean == pytest.approx(50.0 / 1250.0)

    def test_rollouts_are_the_samples(self, spiked_results):
        """Each rollout contributes the mean over its steps, and no more.

        Every step costs 1300 µs in pink and 1250 µs in pinker, except one
        step of pink's second rollout which spiked to 9300
        µs. Two rollouts therefore differ by -50 µs and one by -2050 µs,
        whose mean is what the report states — and whose spread is what
        the interval is about.
        """
        pink_us = (1300.0 + 3300.0 + 1300.0) / 3
        difference = spiked_results.step_relative_diff()
        assert difference.mean == pytest.approx(
            (-50.0 - 2050.0 - 50.0) / 3 / pink_us
        )
        assert difference.low < -2050.0 / pink_us < difference.high

    def test_interference_widens_rather_than_hides(
        self, spiked_results, flat_results
    ):
        """A rollout with an outlier shows up as uncertainty, not as a result.

        The rollouts without one agree on -50 µs, which the
        interval covers comfortably: this run cannot tell -50 from -2050,
        and says so rather than picking one.
        """
        pink_us = (1300.0 + 3300.0 + 1300.0) / 3
        spiked = spiked_results.step_relative_diff()
        flat = flat_results.step_relative_diff()
        assert spiked.half_width > 1000.0 / pink_us
        assert spiked.low < -50.0 / pink_us < spiked.high
        # Rollouts that agree leave nothing to be uncertain about
        assert flat.half_width == pytest.approx(0.0)

    def test_relative_to_the_step(self, spiked_results):
        """The difference is put back in the scale of a step.

        Outlier aside, a step costs 1300 µs in pink and 1250 µs in pinker,
        hence 50 µs less. The rollout with the outlier drags the mean down to
        -2050 µs, a third of the way, and Pink's mean step up to 1967 µs,
        which is the scale the difference is put back in. The whole
        interval scales with the mean, that scale being taken as exact.
        """
        pink_us = (1300.0 + 3300.0 + 1300.0) / 3
        difference_us = confidence_interval(np.array([-50.0, -2050.0, -50.0]))
        relative = spiked_results.step_relative_diff()
        assert relative.mean == pytest.approx(difference_us.mean / pink_us)
        assert relative.low == pytest.approx(difference_us.low / pink_us)
        assert relative.high == pytest.approx(difference_us.high / pink_us)


class TestReport:
    """Tests for the report published in the README."""

    @staticmethod
    def make_results(**kwargs) -> Results:
        """Results of a run, with overridable fields."""
        fields = {
            "date": "2026-07-14",
            "machine": "x86_64",
            "dt": 0.005,
            "qpsolver": "clarabel",
            "rollouts": NB_ROLLOUTS,
            "cpus": "3",
            "provenance": None,
            "versions": {"pink": "pink 4.2.0", "pinker": "pinker 0.1.0"},
            "scenarios": {},
        }
        fields.update(kwargs)
        return Results(**fields)

    @pytest.fixture
    def flat_report(self, flat_results):
        """Report on a flat run: rollouts all agree, hence exact intervals."""
        return Report(self.make_results(scenarios={"ur3": flat_results}))

    @staticmethod
    def scenario_row(markdown: str, name: str) -> list:
        """Cells of the row of a scenario, stripped of their padding."""
        row = next(
            line
            for line in markdown.splitlines()
            if line.startswith(f"| {name} ")
        )
        return [cell.strip() for cell in row.strip("|").split("|")]

    def test_scenario_row(self, flat_report):
        """A scenario that ran is a row of the table.

        Every step costs 1.30 ms in pink and 1.25 ms in pinker: 50 µs less,
        which is 3.85% of a step. Cheaper is never a failure, so the
        perf check passes whatever the margin, and the IK check
        passes, the problems being within tolerance of each other.
        """
        markdown = flat_report.to_markdown()
        assert self.scenario_row(markdown, "ur3") == [
            "ur3",
            "6",
            "1e-12",
            PASS_MARK,
            "1.30 ± 0.00",
            "1.25 ± 0.00",
            "-3.8",
            PASS_MARK,
        ]

    def test_column_headers(self, flat_report):
        """Each number gets its own column, units in the header.

        Each of the two checks of the benchmark follows the columns it
        reads: the IK check the max QP distance, the perf check the step
        durations and their relative change.
        """
        markdown = flat_report.to_markdown()
        header = next(
            line
            for line in markdown.splitlines()
            if line.startswith("| scenario ")
        )
        assert [cell.strip() for cell in header.strip("|").split("|")] == [
            "scenario",
            "nv",
            "max QP distance",
            "IK check",
            "Pink step (ms)",
            "Pinker step (ms)",
            "step var. (%)",
            "perf check",
        ]

    def test_step_columns_are_rounded_to_two_decimals(self):
        """Steps read in milliseconds to two decimals, mean and half-width.

        Rollouts of 1014.38, 1018 and 1021.62 µs average 1.018 ms, give or
        take 0.009: a run does not know a step to the microsecond, so the
        column rounds both to 1.02 ± 0.01 rather than spelling digits the
        interval does not support.
        """
        run = self.make_results(
            scenarios={
                "ur3": scenario_result(
                    pink_timings=[
                        [1014.38] * NB_STEPS,
                        [1018.0] * NB_STEPS,
                        [1021.62] * NB_STEPS,
                    ],
                    pinker_timings=[[1250] * NB_STEPS] * NB_ROLLOUTS,
                )
            }
        )
        cells = self.scenario_row(Report(run).to_markdown(), "ur3")
        assert cells[4] == "1.02 ± 0.01"

    def test_step_columns_carry_their_uncertainty(self, spiked_results):
        """The step columns are means over rollouts, with their interval.

        pink's outlier drags its mean step up to 1.97 ms and widens its
        interval to nearly 3 ms: the column shows both, rather than hiding
        the outlier behind a robust figure.
        """
        run = self.make_results(scenarios={"ur3": spiked_results})
        cells = self.scenario_row(Report(run).to_markdown(), "ur3")
        assert cells[4].startswith("1.97 ± 2.")
        assert cells[5] == "1.25 ± 0.00"

    def test_unresolved_row(self, spiked_results):
        """A scenario the run cannot conclude on is marked as such.

        pink's outlier leaves the difference somewhere between
        -2050 and -50 µs, which spans the +3% margin several times over:
        the IK check passes, the perf check is unresolved. The step
        variation column shows the mean only; the interval the check
        read is not in the table.
        """
        run = self.make_results(scenarios={"ur3": spiked_results})
        cells = self.scenario_row(Report(run).to_markdown(), "ur3")
        assert cells[3] == PASS_MARK
        assert cells[6] == "-36.4"  # no ± here: the mean only
        assert cells[7] == UNRESOLVED_MARK

    def test_passing_row_within_the_margin(self):
        """Identical timings on both sides pass, whatever the margin."""
        same = [[1300] * NB_STEPS] * NB_ROLLOUTS
        run = self.make_results(scenarios={"ur3": scenario_result(same, same)})
        cells = self.scenario_row(Report(run).to_markdown(), "ur3")
        assert cells[4:] == [
            "1.30 ± 0.00",
            "1.30 ± 0.00",
            "+0.0",
            PASS_MARK,
        ]

    def test_timings_tolerance_moves_the_perf_check(self, monkeypatch):
        """The timings tolerance is a setting of the report, not of the run.

        It is read where a past run is re-rendered, not stored with the
        timings, so tightening it re-decides every scenario without
        benchmarking again.
        """
        # Every step costs 1300 µs in pink and 1350 µs in pinker: +3.85%,
        # which a 20% margin grants and a 3% one does not.
        slower = self.make_results(
            scenarios={
                "ur3": scenario_result(
                    [[1300] * NB_STEPS] * NB_ROLLOUTS,
                    [[1350] * NB_STEPS] * NB_ROLLOUTS,
                )
            }
        )
        set_timings_tolerance_pct(monkeypatch, 20.0)
        lenient = self.scenario_row(Report(slower).to_markdown(), "ur3")
        set_timings_tolerance_pct(monkeypatch, 3.0)
        strict = self.scenario_row(Report(slower).to_markdown(), "ur3")
        assert lenient[4:7] == strict[4:7]
        assert strict[4:7] == ["1.30 ± 0.00", "1.35 ± 0.00", "+3.8"]
        assert lenient[7] == PASS_MARK
        assert strict[7] == FAIL_MARK

    def test_qp_tolerance_moves_the_ik_check(self, flat_results, monkeypatch):
        """The QP tolerance is a setting of the report too.

        Distances are recorded as they were measured, and read against
        the tolerance when the run is rendered: a scenario that passed at
        1e-9 fails at 1e-13 without benchmarking again. The perf
        check is its own test, and does not move with it.
        """
        run = self.make_results(scenarios={"ur3": flat_results})
        set_num_tol(monkeypatch, 1e-9)
        lenient = self.scenario_row(Report(run).to_markdown(), "ur3")
        set_num_tol(monkeypatch, 1e-13)
        strict = self.scenario_row(Report(run).to_markdown(), "ur3")
        assert lenient[2] == strict[2] == "1e-12"
        assert lenient[3] == PASS_MARK
        assert strict[3] == FAIL_MARK
        assert lenient[7] == strict[7] == PASS_MARK

    def test_integration_mismatch_is_listed(self, monkeypatch):
        """A failure of the check the table has no column for is spelled out.

        The IK check fails on it, so the reader is told why, under
        the table, with how far apart the two libraries landed.
        """
        set_num_tol(monkeypatch, 1e-9)
        drifted = scenario_result(
            [[1300] * NB_STEPS] * NB_ROLLOUTS,
            [[1250] * NB_STEPS] * NB_ROLLOUTS,
            qp_dist=1e-12,
            integration_dist=3e-6,
        )
        run = self.make_results(scenarios={"ur3": drifted})
        assert Report(run).integration_mismatches() == {
            "ur3": pytest.approx(3e-6)
        }
        markdown = Report(run).to_markdown()
        cells = self.scenario_row(markdown, "ur3")
        assert cells[3] == FAIL_MARK
        assert cells[7] == PASS_MARK
        assert "integrate to differ by more than the 1e-09" in markdown
        assert "- ur3: up to 3e-06" in markdown

    def test_settings_are_stated_with_the_conclusion(
        self, flat_report, monkeypatch
    ):
        """The conclusion states the thresholds it was drawn against."""
        set_timings_tolerance_pct(monkeypatch, 5.0)
        set_num_tol(monkeypatch, 1e-10)
        markdown = flat_report.to_markdown()
        assert "numerical variations less than 1e-10" in markdown
        assert "timings variations less than 5%" in markdown
        assert f"{NB_ROLLOUTS} rollouts per scenario" in markdown

    def test_run_sentence(self, flat_report):
        """The report opens on what was compared, and under what conditions.

        A reader lands on the versions the run compared and the conditions
        it measured them in, before anything it concludes.
        """
        first = flat_report.to_markdown().splitlines()[0]
        assert first.startswith(
            "Here are the results from running the benchmark on 2026-07-14"
        )
        assert "(x86_64)" in first
        assert "comparing pinker 0.1.0 to pink 4.2.0" in first
        assert "QP solver is clarabel" in first
        assert f"{NB_ROLLOUTS} rollouts per scenario" in first
        assert "pinned to CPU 3" in first

    def test_conclusion_comes_before_the_table(self, flat_report):
        """A reader is told what the run concludes before how it got there."""
        markdown = flat_report.to_markdown()
        conclusion = markdown.split("| scenario")[0]
        assert "we conclude that:" in conclusion
        assert (
            f"1. **Same IK problems:** {PASS_MARK}, numerical variations"
            " less than" in conclusion
        )
        assert (
            f"2. **Same performance:** {PASS_MARK}, timings variations less"
            " than" in conclusion
        )
        assert "Here are the overall statistics scenario by scenario:" in (
            conclusion
        )
        assert markdown.rstrip().endswith(
            "The data corresponding to this run is available in the"
            " `results/` directory."
        )

    def test_conclusion_is_the_whole_bench(self, flat_results, monkeypatch):
        """A criterion holds over the bench when it holds on every scenario.

        One scenario failing its IK check fails the bench on that
        criterion, whatever the others say, and leaves the other criterion
        alone.
        """
        set_num_tol(monkeypatch, 1e-9)
        drifted = scenario_result(
            pink_timings=[[1300] * NB_STEPS] * NB_ROLLOUTS,
            pinker_timings=[[1250] * NB_STEPS] * NB_ROLLOUTS,
            qp_dist=1e-6,
        )
        run = self.make_results(
            scenarios={"ur3": flat_results, "edo": drifted}
        )
        assert Report(run).conclusion() == {"ik": FAIL_MARK, "perf": PASS_MARK}
        markdown = Report(run).to_markdown()
        # A failed criterion states what was measured, not the bound that
        # did not hold: "less than 1e-9" would be false here.
        assert (
            f"1. **Same IK problems:** {FAIL_MARK}, numerical variations"
            " up to 1e-06" in markdown
        )
        assert (
            f"2. **Same performance:** {PASS_MARK}, timings variations less"
            " than" in markdown
        )

    def test_conclusion_of_an_unresolved_bench(
        self, flat_results, spiked_results
    ):
        """One scenario the run cannot conclude on leaves it unresolved.

        The spiked rollout spans the margin, so the bench is unresolved on
        performance even though the other scenario passes.
        """
        run = self.make_results(
            scenarios={"ur3": flat_results, "edo": spiked_results}
        )
        assert Report(run).conclusion() == {
            "ik": PASS_MARK,
            "perf": UNRESOLVED_MARK,
        }
        # Unresolved rules nothing out: the margin may well be exceeded.
        assert (
            f"2. **Same performance:** {UNRESOLVED_MARK}, timings variations"
            " possibly above" in Report(run).to_markdown()
        )

    def test_conclusion_of_an_empty_run(self):
        """A run with no scenario concludes nothing, rather than passing."""
        run = self.make_results(scenarios={})
        assert Report(run).conclusion() == {
            "ik": UNRESOLVED_MARK,
            "perf": UNRESOLVED_MARK,
        }

    def test_table_alone_is_the_table_alone(self, flat_report):
        """The table can be had without the prose that introduces it.

        This is what a run prints on the terminal once it is done, and
        what the README embeds under its legend.
        """
        lines = flat_report.table()
        assert all(line.startswith("|") for line in lines)
        assert lines[0].startswith("| scenario ")


class TestTableLayout:
    """Tests for how the table lays out in the Markdown source.

    The README carries the table as text, and is read unrendered as often
    as rendered, so its columns are expected to line up in the source.
    """

    @staticmethod
    def report_on(**scenarios) -> Report:
        """Report on the given scenarios, one per keyword."""
        return Report(TestReport.make_results(scenarios=scenarios))

    @staticmethod
    def pipe_columns(line: str) -> List[int]:
        """Columns the cell separators of a line sit at, as printed.

        Args:
            line: Line of the table.

        Returns:
            Monospace column of each ``|`` of the line, the marks counting
            for the two columns they take.
        """
        return [
            wcwidth.wcswidth(line[:index])
            for index, char in enumerate(line)
            if char == "|"
        ]

    def test_columns_are_padded_to_their_contents(self, flat_results):
        """Cells are padded to the widest of their column, and no further.

        A failing scenario rides along so that a column holding two
        different marks is laid out the same on both rows.
        """
        failing = scenario_result(
            pink_timings=[[1300] * NB_STEPS] * NB_ROLLOUTS,
            pinker_timings=[[1350] * NB_STEPS] * NB_ROLLOUTS,
            qp_dist=1e-6,
        )
        table = self.report_on(ur3=flat_results, edo=failing).table()
        assert table == [
            "| scenario | nv | max QP distance | IK check | Pink step (ms) |"
            " Pinker step (ms) | step var. (%) | perf check |",
            "|:---------|---:|----------------:|:---------|---------------:|"
            "-----------------:|--------------:|:-----------|",
            f"| ur3      |  6 |           1e-12 | {PASS_MARK}       |"
            f"    1.30 ± 0.00 |      1.25 ± 0.00 |          -3.8 |"
            f" {PASS_MARK}         |",
            f"| edo      |  6 |           1e-06 | {FAIL_MARK}       |"
            f"    1.30 ± 0.00 |      1.35 ± 0.00 |          +3.8 |"
            f" {FAIL_MARK}         |",
        ]

    def test_alignment_is_declared_per_column(self, flat_results):
        """The separator row states which way each column reads.

        Names and marks read from the left, every number from the right,
        which is what the colons of the separator row declare.
        """
        separator = self.report_on(ur3=flat_results).table()[1]
        sides = [
            (cell.startswith(":"), cell.endswith(":"))
            for cell in separator.strip("|").split("|")
        ]
        left, right = (True, False), (False, True)
        assert sides == [left, right, right, left, right, right, right, left]

    def test_a_mark_takes_two_columns(self, flat_results, spiked_results):
        """The marks are emoji: one character each, but two columns wide.

        Padding them on their length would leave the Markdown source
        ragged, so every line of the table is expected to break at the
        same columns, whichever marks its row carries. This is what the
        wcwidth dependency buys, and what dropping it would undo.
        """
        table = self.report_on(ur3=flat_results, edo=spiked_results).table()
        # The spiked rollouts straddle the margin, so the unresolved mark
        # is in there alongside the passing one: three widths to line up.
        assert UNRESOLVED_MARK in table[3]
        assert PASS_MARK in table[2]
        assert all(wcwidth.wcswidth(mark) == 2 for mark in MARKS)
        header, separator, *scenario_rows = table
        for row in [separator, *scenario_rows]:
            assert self.pipe_columns(row) == self.pipe_columns(header)
