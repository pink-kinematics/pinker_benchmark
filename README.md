# Pinker benchmark

This benchmark validates the performance of [Pinker](https://github.com/pink-kinematics/pinker) against [Pink](https://github.com/pink-kinematics/pink) using the [pink motions](https://github.com/pink-kinematics/pink_motions/) library of robot trajectories.

## Scope

Our goal is to make sure that there was no regression from Pink to Pinker. We check two properties:

1. **Same IK problems:** given the same configuration and tasks, Pink and Pinker produce the same quadratic program, resulting in the same velocity.
2. **Same performance:** Pinker has the same (or lower) computation times than Pink on the target architecture.

The target architecture reported below is the Raspberry Pi 4 Model B.

## Results

<!-- BEGIN BENCHMARK RESULTS -->

Here are the results from running the benchmark on 2026-09-22 (aarch64, commit b63fb5810) comparing pinker 0.1.0-alpha to pink 4.4.0 (pinocchio 4.1.0). QP solver clarabel, 10 rollouts per scenario, pinned to CPU 3.

From the data collected during this evaluation, we conclude that:

1. **Same IK problems:** ✅, numerical variations less than 1e-09
2. **Same performance:** ✅, timings variations less than 3%

Here are the overall statistics scenario by scenario:

| scenario      | nv | max QP distance | IK check | Pink step (ms) | Pinker step (ms) | step var. (%) | perf check |
|:--------------|---:|----------------:|:---------|---------------:|-----------------:|--------------:|:-----------|
| edo           |  6 |           6e-15 | ✅       |    1.97 ± 0.01 |      1.95 ± 0.01 |          -0.9 | ✅         |
| fanuc         |  6 |           9e-14 | ✅       |    2.16 ± 0.01 |      2.15 ± 0.01 |          -0.5 | ✅         |
| gen2          |  6 |           5e-15 | ✅       |    2.13 ± 0.01 |      2.11 ± 0.01 |          -0.7 | ✅         |
| gen3          |  7 |           1e-14 | ✅       |    2.16 ± 0.01 |      2.15 ± 0.01 |          -0.8 | ✅         |
| iiwa14        |  7 |           3e-15 | ✅       |    2.22 ± 0.01 |      2.21 ± 0.01 |          -0.5 | ✅         |
| panda         |  9 |           1e-15 | ✅       |    2.36 ± 0.01 |      2.35 ± 0.01 |          -0.6 | ✅         |
| poppy_ergo_jr |  6 |           2e-15 | ✅       |    1.96 ± 0.01 |      1.94 ± 0.01 |          -0.6 | ✅         |
| ur10          |  6 |           4e-15 | ✅       |    2.15 ± 0.01 |      2.14 ± 0.01 |          -0.4 | ✅         |
| ur3           |  6 |           3e-15 | ✅       |    2.14 ± 0.01 |      2.13 ± 0.01 |          -0.6 | ✅         |
| ur5           |  6 |           3e-15 | ✅       |    2.13 ± 0.01 |      2.12 ± 0.01 |          -0.4 | ✅         |
| z1            |  6 |           2e-14 | ✅       |    2.13 ± 0.01 |      2.12 ± 0.01 |          -0.6 | ✅         |
| atlas_drc     | 36 |           3e-13 | ✅       |    3.88 ± 0.01 |      3.85 ± 0.01 |          -0.7 | ✅         |
| atlas_v4      | 36 |           3e-13 | ✅       |    3.87 ± 0.01 |      3.86 ± 0.01 |          -0.3 | ✅         |
| draco3        | 33 |           5e-14 | ✅       |    3.71 ± 0.01 |      3.70 ± 0.01 |          -0.4 | ✅         |
| ergocub       | 63 |           1e-14 | ✅       |    7.73 ± 0.03 |      7.60 ± 0.03 |          -1.7 | ✅         |
| h1            | 25 |           1e-14 | ✅       |    3.31 ± 0.01 |      3.33 ± 0.01 |          +0.5 | ✅         |
| icub          | 38 |           2e-13 | ✅       |    4.26 ± 0.01 |      4.18 ± 0.01 |          -2.0 | ✅         |
| jaxon         | 44 |           1e-13 | ✅       |    4.11 ± 0.01 |      4.08 ± 0.01 |          -0.7 | ✅         |
| jvrc          | 50 |           5e-13 | ✅       |    4.59 ± 0.01 |      4.55 ± 0.01 |          -0.7 | ✅         |
| r2            | 62 |           2e-14 | ✅       |    5.65 ± 0.02 |      5.59 ± 0.02 |          -1.0 | ✅         |
| romeo         | 67 |           5e-14 | ✅       |    5.07 ± 0.03 |      4.99 ± 0.03 |          -1.7 | ✅         |
| sigmaban      | 26 |           6e-14 | ✅       |    3.01 ± 0.01 |      3.02 ± 0.01 |          +0.4 | ✅         |
| talos         | 50 |           9e-12 | ✅       |    4.31 ± 0.01 |      4.28 ± 0.01 |          -0.7 | ✅         |
| valkyrie      | 65 |           4e-15 | ✅       |    5.44 ± 0.03 |      5.37 ± 0.03 |          -1.2 | ✅         |
| bolt          | 12 |           2e-15 | ✅       |    2.58 ± 0.01 |      2.62 ± 0.01 |          +1.6 | ✅         |
| cassie        | 22 |           3e-15 | ✅       |    3.31 ± 0.01 |      3.33 ± 0.01 |          +0.6 | ✅         |
| spryped       | 14 |           8e-15 | ✅       |    2.56 ± 0.01 |      2.60 ± 0.01 |          +1.5 | ✅         |

The data corresponding to this run is available in the `results/` directory.

<!-- END BENCHMARK RESULTS -->

## Usage

We use [pixi](https://pixi.sh) to handle dependencies and run tasks. To regenerate the above results, simply call:

```console
pixi run benchmark
```

This command runs the whole benchmark on your machine, storing measurements in the `results/` sub-directory and updating the Results section above.
