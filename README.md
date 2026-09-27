# Pinker benchmark

This benchmark validates the performance of [Pinker](https://github.com/pink-kinematics/pinker) against [Pink](https://github.com/pink-kinematics/pink) using the [pink motions](https://github.com/pink-kinematics/pink_motions/) library of robot trajectories.

## Scope

Our goal is to make sure that there was no regression from Pink to Pinker. We check two properties:

1. **Same IK problems:** given the same configuration and tasks, Pink and Pinker produce the same quadratic program, resulting in the same velocity.
2. **Same performance:** Pinker has the same (or lower) computation times than Pink on the target architecture.

The target architecture reported below is the Raspberry Pi 4 Model B.

## Usage

This benchmark uses [pixi](https://pixi.sh) to handle dependencies and run tasks. To regenerate results, call:

```console
pixi run benchmark
```

This command runs all scenarios on your machine, storing measurements in the `results/` sub-directory and updating the Results section below automatically.

## Results

<!-- BEGIN BENCHMARK RESULTS -->

Here are the results from running the benchmark on 2026-09-27 (aarch64, commit 440f2f80b) comparing pinker 0.1.0 to pink 4.4.0 (pinocchio 4.1.0). QP solver is clarabel, 10 rollouts per scenario, pinned to CPU 3.

From the data collected during this evaluation, we conclude that:

1. **Same IK problems:** ✅, numerical variations less than 1e-09
2. **Same performance:** ✅, timings variations less than 3%

Here are the statistics scenario by scenario:

| scenario      | nv | max QP distance | IK check | Pink step (ms) | Pinker step (ms) | step var. (%) | perf check |
|:--------------|---:|----------------:|:---------|---------------:|-----------------:|--------------:|:-----------|
| edo           |  6 |           6e-15 | ✅       |    1.96 ± 0.01 |      1.94 ± 0.01 |          -0.9 | ✅         |
| fanuc         |  6 |           9e-14 | ✅       |    2.16 ± 0.01 |      2.15 ± 0.01 |          -0.6 | ✅         |
| gen2          |  6 |           5e-15 | ✅       |    2.12 ± 0.01 |      2.10 ± 0.01 |          -0.6 | ✅         |
| gen3          |  7 |           1e-14 | ✅       |    2.15 ± 0.01 |      2.13 ± 0.01 |          -0.8 | ✅         |
| iiwa14        |  7 |           3e-15 | ✅       |    2.21 ± 0.01 |      2.19 ± 0.01 |          -0.5 | ✅         |
| panda         |  9 |           1e-15 | ✅       |    2.36 ± 0.01 |      2.34 ± 0.01 |          -0.6 | ✅         |
| poppy_ergo_jr |  6 |           2e-15 | ✅       |    1.95 ± 0.01 |      1.94 ± 0.01 |          -0.7 | ✅         |
| ur10          |  6 |           4e-15 | ✅       |    2.14 ± 0.01 |      2.13 ± 0.01 |          -0.4 | ✅         |
| ur3           |  6 |           3e-15 | ✅       |    2.13 ± 0.01 |      2.12 ± 0.01 |          -0.6 | ✅         |
| ur5           |  6 |           3e-15 | ✅       |    2.12 ± 0.01 |      2.11 ± 0.01 |          -0.4 | ✅         |
| z1            |  6 |           2e-14 | ✅       |    2.13 ± 0.01 |      2.12 ± 0.01 |          -0.6 | ✅         |
| atlas_drc     | 36 |           3e-13 | ✅       |    3.86 ± 0.02 |      3.83 ± 0.01 |          -0.7 | ✅         |
| atlas_v4      | 36 |           3e-13 | ✅       |    3.85 ± 0.01 |      3.83 ± 0.01 |          -0.4 | ✅         |
| draco3        | 33 |           5e-14 | ✅       |    3.68 ± 0.01 |      3.67 ± 0.01 |          -0.4 | ✅         |
| ergocub       | 63 |           1e-14 | ✅       |    7.70 ± 0.03 |      7.57 ± 0.03 |          -1.7 | ✅         |
| h1            | 25 |           1e-14 | ✅       |    3.29 ± 0.01 |      3.30 ± 0.01 |          +0.4 | ✅         |
| icub          | 38 |           2e-13 | ✅       |    4.23 ± 0.01 |      4.15 ± 0.01 |          -2.0 | ✅         |
| jaxon         | 44 |           1e-13 | ✅       |    4.08 ± 0.01 |      4.05 ± 0.01 |          -0.8 | ✅         |
| jvrc          | 50 |           5e-13 | ✅       |    4.56 ± 0.01 |      4.53 ± 0.01 |          -0.8 | ✅         |
| r2            | 62 |           2e-14 | ✅       |    5.61 ± 0.01 |      5.55 ± 0.02 |          -1.1 | ✅         |
| romeo         | 67 |           5e-14 | ✅       |    5.04 ± 0.03 |      4.95 ± 0.03 |          -1.7 | ✅         |
| sigmaban      | 26 |           6e-14 | ✅       |    2.99 ± 0.01 |      3.00 ± 0.01 |          +0.3 | ✅         |
| talos         | 50 |           9e-12 | ✅       |    4.29 ± 0.01 |      4.26 ± 0.01 |          -0.8 | ✅         |
| valkyrie      | 65 |           4e-15 | ✅       |    5.40 ± 0.03 |      5.32 ± 0.03 |          -1.3 | ✅         |
| bolt          | 12 |           2e-15 | ✅       |    2.57 ± 0.01 |      2.61 ± 0.01 |          +1.4 | ✅         |
| cassie        | 22 |           3e-15 | ✅       |    3.30 ± 0.01 |      3.31 ± 0.01 |          +0.4 | ✅         |
| spryped       | 14 |           8e-15 | ✅       |    2.56 ± 0.01 |      2.59 ± 0.01 |          +1.2 | ✅         |

The data corresponding to this run is available in the `results/` directory.

<!-- END BENCHMARK RESULTS -->
