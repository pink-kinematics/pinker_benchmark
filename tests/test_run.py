# SPDX-License-Identifier: Apache-2.0

"""Tests for the main run function."""

import os

from pinker_benchmark import run
from pinker_benchmark.results import SAMPLE_COLUMNS
from pinker_benchmark.run import (
    benchmark_scenario,
    format_duration,
    pin_to_cpus,
)


class TestBenchmarkScenario:
    """Tests for the rollout of one scenario."""

    def test_rollouts_accumulate_column_by_column(self, monkeypatch):
        """Every step of every rollout lands in the lists of its columns.

        A coarse timestep keeps the test short: the scenario is 10 s
        long, so it rolls out in 20 steps rather than 2000.
        """
        monkeypatch.setattr(run, "DT", 0.5)
        samples = {column: [] for column in SAMPLE_COLUMNS}
        first = benchmark_scenario("ur3", samples)
        second = benchmark_scenario("ur3", samples)
        assert first["steps"] == second["steps"] == 20
        assert first["nv"] == 6
        for column in SAMPLE_COLUMNS:
            assert len(samples[column]) == 40
        # Both rollouts take the same steps, so they land at the same place
        assert first["q_final"] == second["q_final"]


class TestFormatDuration:
    """Tests for the duration a run reports when it is done."""

    def test_every_unit_shows_up(self):
        """A sweep takes hours, so all three units are spelled out."""
        assert format_duration(3 * 3600 + 25 * 60 + 7) == "3 h 25 min 7 s"

    def test_short_run(self):
        """Debugging runs are short, and say so rather than saying 0."""
        assert format_duration(42.7) == "0 h 0 min 42 s"

    def test_rounded_down_to_the_second(self):
        """Nothing the benchmark measures is timed by this clock."""
        assert format_duration(59.999) == "0 h 0 min 59 s"


class TestPinToCpus:
    """Tests for the cores a run confines itself to."""

    def test_pins_to_the_setting(self, monkeypatch):
        """A machine with cores to spare runs on the ones asked for."""
        pinned = {}
        monkeypatch.setattr(run, "CPUS", (3,))
        monkeypatch.setattr(os, "cpu_count", lambda: 4)
        monkeypatch.setattr(
            os, "sched_setaffinity", lambda pid, cpus: pinned.update(cpus=cpus)
        )
        assert pin_to_cpus() == "3"
        assert pinned["cpus"] == {3}

    def test_too_few_cores(self, monkeypatch):
        """A smaller machine runs unpinned, and says so rather than lying.

        The report states the setup a run actually had, so a run that
        could not pin must not claim it did.
        """
        monkeypatch.setattr(run, "CPUS", (3,))
        monkeypatch.setattr(os, "cpu_count", lambda: 2)
        assert pin_to_cpus() == ""

    def test_pinning_disabled(self, monkeypatch):
        """An empty setting is how pinning is turned off."""
        monkeypatch.setattr(run, "CPUS", ())
        assert pin_to_cpus() == ""
