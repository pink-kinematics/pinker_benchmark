# SPDX-License-Identifier: Apache-2.0

"""Publish benchmark results to the README."""

import os
from typing import Dict, List, Optional

import tabulate

from .checks import (
    FAIL_MARK,
    PASS_MARK,
    UNRESOLVED_MARK,
    ik_check_mark,
    perf_check_mark,
)
from .results import (
    METADATA_PATH,
    README_PATH,
    Results,
    check_measurements,
    last_measurements_path,
)
from .settings import NUM_TOL, TIMINGS_TOLERANCE_PCT

# The results table is generated between these markers in the README.
BEGIN_MARKER = "<!-- BEGIN BENCHMARK RESULTS -->"
END_MARKER = "<!-- END BENCHMARK RESULTS -->"


class Report:
    """Report on the results of a run to the README.

    Attributes:
        results: Results of the run to report on.
    """

    results: Results

    def __init__(self, results: Results):
        """Create a report on the results of a run.

        Args:
            results: Results of the run the report is about.
        """
        self.results = results

    def checks(self) -> Dict[str, Dict[str, str]]:
        """Conclude on each scenario, one mark per criterion.

        Returns:
            The IK and perf check of each scenario, by name, under the keys
            ``"ik"`` and ``"perf"``.
        """
        checks = {}
        for name, scenario in self.results.scenarios.items():
            qp_dist = scenario.max_dist("qp_dist")
            integration_dist = scenario.max_dist("integration_dist")
            checks[name] = {
                "ik": ik_check_mark(qp_dist, integration_dist),
                "perf": perf_check_mark(scenario.step_relative_diff()),
            }
        return checks

    def conclusion(self) -> Dict[str, str]:
        """Conclude on the run as a whole, one mark per criterion.

        Returns:
            The mark of each criterion over every scenario, under the keys
            ``"ik"`` and ``"perf"``. A run with no scenario concludes
            nothing, and is unresolved on both.
        """
        conclusion = {}
        checks = self.checks()
        for criterion in ("ik", "perf"):
            marks = [check[criterion] for check in checks.values()]
            if not marks or FAIL_MARK in marks:
                conclusion[criterion] = FAIL_MARK if marks else UNRESOLVED_MARK
            elif UNRESOLVED_MARK in marks:
                conclusion[criterion] = UNRESOLVED_MARK
            else:
                conclusion[criterion] = PASS_MARK
        return conclusion

    def max_dist(self) -> float:
        """Largest distance between the two libraries over the whole bench.

        Returns:
            Largest distance in any scenario, between both the QPs and the
            configurations after integration. Zero when no scenario ran.
        """
        return max(
            (
                max(
                    scenario.max_dist("qp_dist"),
                    scenario.max_dist("integration_dist"),
                )
                for scenario in self.results.scenarios.values()
            ),
            default=0.0,
        )

    def table(self) -> List[str]:
        """Compare the two libraries scenario by scenario, as a table.

        Returns:
            Lines of the Markdown table, empty if no scenario ran.
        """
        rows: List[List[str]] = []
        checks = self.checks()
        for name, scenario in self.results.scenarios.items():
            steps = {}
            for library in ("pink", "pinker"):
                step_timings = scenario.step_timings(library)
                mean_ms = 1e-3 * step_timings.mean
                half_width_ms = 1e-3 * step_timings.half_width
                steps[library] = f"{mean_ms:.2f} ± {half_width_ms:.2f}"
            step_relative_diff = scenario.step_relative_diff()
            rows.append(
                [
                    name,
                    str(scenario.nv),
                    f"{scenario.max_dist('qp_dist'):.0e}",
                    checks[name]["ik"],
                    steps["pink"],
                    steps["pinker"],
                    f"{100 * step_relative_diff.mean:+.1f}",
                    checks[name]["perf"],
                ]
            )
        if not rows:
            return []
        tabulate.MIN_PADDING = 0
        return tabulate.tabulate(
            rows,
            headers=[
                "scenario",
                "nv",
                "max QP distance",
                "IK check",
                "Pink step (ms)",
                "Pinker step (ms)",
                "step var. (%)",
                "perf check",
            ],
            colalign=[
                "left",
                "right",
                "right",
                "left",
                "right",
                "right",
                "right",
                "left",
            ],
            tablefmt="pipe",
            disable_numparse=True,
        ).splitlines()

    def integration_mismatches(self) -> Dict[str, float]:
        """Scenarios where the two libraries integrated to different places.

        Both libraries integrate the same velocity from the same
        configuration at every step, so they should land on the same one:
        this is checked against the same tolerance as the problems they
        build, but it is not a column of the table, so the scenarios that
        fail it are listed under it, with how far apart they landed.

        Returns:
            Largest integration distance of each scenario where it exceeds
            the tolerance.
        """
        mismatches = {}
        for name, scenario in self.results.scenarios.items():
            dist = scenario.max_dist("integration_dist")
            if dist > NUM_TOL:
                mismatches[name] = dist
        return mismatches

    def to_markdown(self) -> str:
        """Render the report, as the README publishes it.

        Returns:
            Section of the README reporting the run: the conditions it ran
            in, its conclusion on each criterion, the table itself, and
            what that table cannot show.
        """
        results = self.results
        pink_version = results.versions.get("pink", "pink")
        pinker_version = results.versions.get("pinker", "pinker")
        provenance = results.provenance
        commit = ""
        if provenance is not None:
            dirty = ", dirty working tree" if provenance.dirty else ""
            commit = f", commit {provenance.commit[:9]}{dirty}"
        margin = f"{TIMINGS_TOLERANCE_PCT:.0f}%"
        tolerance = f"{NUM_TOL:.0e}"
        conclusion = self.conclusion()
        if conclusion["ik"] == PASS_MARK:
            ik_fact = f"numerical variations less than {tolerance}"
        else:
            ik_fact = f"numerical variations up to {self.max_dist():.0e}"
        if conclusion["perf"] == PASS_MARK:
            perf_fact = f"timings variations less than {margin}"
        elif conclusion["perf"] == FAIL_MARK:
            perf_fact = f"timings variations above {margin}"
        else:
            perf_fact = f"timings variations possibly above {margin}"
        lines = [
            f"Here are the results from running the benchmark on"
            f" {results.date} ({results.machine}{commit}) comparing"
            f" {pinker_version} to {pink_version}."
            f" QP solver is {results.qpsolver}, {results.rollouts} rollouts"
            f" per scenario. The conclusions are that:",
            "",
            "1. **Pinker produces the same IK problems as Pink:** "
            f"{conclusion['ik']} ({ik_fact})",
            "2. **Pinker has the same performance as Pink:** "
            f"{conclusion['perf']} ({perf_fact})",
            "",
            "Here are the statistics scenario by scenario:",
            "",
        ]
        lines += self.table()
        mismatches = self.integration_mismatches()
        if mismatches:
            lines += [
                "",
                "Scenarios where the configurations the two libraries"
                f" integrate to differ by more than the {tolerance}"
                " tolerance:",
                "",
            ]
            for name, dist in mismatches.items():
                lines.append(f"- {name}: up to {dist:.0e}")
        lines += [
            "",
            "The data corresponding to this run is available in the"
            " `results/` directory.",
        ]
        return "\n".join(lines) + "\n"

    def update_readme(self, readme: str) -> str:
        """Replace the results section of a README with this report.

        Args:
            readme: Contents of the README.

        Returns:
            Contents of the README, results updated.

        Raises:
            ValueError: If the README has no results section to update.
        """
        if BEGIN_MARKER not in readme or END_MARKER not in readme:
            raise ValueError(
                f"{README_PATH} has no {BEGIN_MARKER} ... {END_MARKER} section"
            )
        start = readme.index(BEGIN_MARKER)
        end = readme.index(END_MARKER) + len(END_MARKER)
        return (
            readme[:start]
            + f"{BEGIN_MARKER}\n\n{self.to_markdown()}\n{END_MARKER}"
            + readme[end:]
        )


def publish_results(measurements_path: Optional[str] = None) -> None:
    """Publish the results of a run in the README.

    Args:
        measurements_path: Path to the measurements of the run. Defaults
            to those of the last run, as its metadata records them.

    Raises:
        FileNotFoundError: If no run is on record to publish.
    """
    if measurements_path is None:
        measurements_path = last_measurements_path()
    if measurements_path is None:
        raise FileNotFoundError(
            f"no run on record in {os.path.basename(METADATA_PATH)}:"
            " run the benchmark first"
        )
    if check_measurements(measurements_path) is False:
        print(
            f"warning: {os.path.basename(measurements_path)} does not"
            f" match the checksum in {os.path.basename(METADATA_PATH)}"
        )
    report = Report(Results.read(measurements_path))
    with open(README_PATH, "r", encoding="utf-8") as handle:
        readme = handle.read()
    updated = report.update_readme(readme)
    if updated != readme:
        with open(README_PATH, "w", encoding="utf-8") as handle:
            handle.write(updated)
        print(f"Updated the results in {README_PATH}")

    # Also print out the results to the standard output
    table = report.table()
    if table:
        print("\n" + "\n".join(table))


if __name__ == "__main__":
    publish_results()
