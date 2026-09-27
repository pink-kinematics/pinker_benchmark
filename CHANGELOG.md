# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-09-27

### Added

- Adapter for [Pink](https://github.com/pink-kinematics/pink) v4.4.0
- Adapter for [Pinker](https://github.com/pink-kinematics/pinker) v1.0.0
- CICD: Run the test suite and the linter on x86-64 and arm64
- Interface to the robot scenarios from [pink motions](https://github.com/pink-kinematics/pink_motions)
- Pin the exact versions of Pink and Pinker and their main dependencies
- checks: Verify that both libraries build the same quadratic program at every step
- checks: Verify that steps cost Pinker no more than a stated margin over Pink
- debug: Script to step through a scenario interactively, optionally displaying it
- pixi: Add `benchmark`, `benchmark-report`, `debug-scenario`, `dev-test`, `dev-lint` and `dev-format` tasks
- provenance: Record the commit under benchmark, don't run when there are uncommitted changes
- report: Compute statistics over repeated rollouts with 95% confidence intervals
- report: Conclude on every scenario and on the run as a whole, unresolved when the data is too thin
- report: Publish a results table to the README, one row per scenario
- results: Store raw measurements in Parquet and the running conditions in separate metadata
- scene: Measure numerical variations between the two libraries
- scene: Measure timings the two libraries take to build problems and integrate velocities
- scene: Step both libraries through every scenario together from the same configuration
- settings: Gather all benchmark parameters in a single module

[unreleased]: https://github.com/pink-kinematics/pinker_benchmark/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/pink-kinematics/pinker_benchmark/releases/tag/v1.0.0
