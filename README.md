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

Here are the results from running the benchmark on 2026-09-27 (aarch64, commit 751da6a89) comparing pinker 1.0.0 to pink 4.4.0 (pinocchio 4.1.0). QP solver is clarabel, 10 rollouts per scenario. The conclusions are that:

1. **Pinker produces the same IK problems as Pink:** ✅ (numerical variations less than 1e-09)
2. **Pinker has the same performance as Pink:** ✅ (timings variations less than 3%)

Here are the statistics scenario by scenario:

| scenario      | nv | max QP distance | IK check | Pink step (ms) | Pinker step (ms) | step var. (%) | perf check |
|:--------------|---:|----------------:|:---------|---------------:|-----------------:|--------------:|:-----------|
| edo           |  6 |           6e-15 | ✅       |    1.99 ± 0.01 |      1.98 ± 0.01 |          -0.6 | ✅         |
| fanuc         |  6 |           9e-14 | ✅       |    2.19 ± 0.01 |      2.18 ± 0.01 |          -0.4 | ✅         |
| gen2          |  6 |           5e-15 | ✅       |    2.14 ± 0.01 |      2.13 ± 0.01 |          -0.4 | ✅         |
| gen3          |  7 |           1e-14 | ✅       |    2.19 ± 0.01 |      2.17 ± 0.01 |          -0.6 | ✅         |
| iiwa14        |  7 |           3e-15 | ✅       |    2.24 ± 0.01 |      2.24 ± 0.01 |          -0.2 | ✅         |
| panda         |  9 |           1e-15 | ✅       |    2.39 ± 0.01 |      2.38 ± 0.01 |          -0.5 | ✅         |
| poppy_ergo_jr |  6 |           2e-15 | ✅       |    1.98 ± 0.01 |      1.97 ± 0.01 |          -0.5 | ✅         |
| ur10          |  6 |           4e-15 | ✅       |    2.17 ± 0.01 |      2.16 ± 0.01 |          -0.3 | ✅         |
| ur3           |  6 |           3e-15 | ✅       |    2.16 ± 0.01 |      2.15 ± 0.01 |          -0.5 | ✅         |
| ur5           |  6 |           3e-15 | ✅       |    2.16 ± 0.01 |      2.15 ± 0.01 |          -0.3 | ✅         |
| z1            |  6 |           2e-14 | ✅       |    2.16 ± 0.01 |      2.15 ± 0.01 |          -0.4 | ✅         |
| atlas_drc     | 36 |           3e-13 | ✅       |    3.89 ± 0.02 |      3.88 ± 0.02 |          -0.5 | ✅         |
| atlas_v4      | 36 |           3e-13 | ✅       |    3.89 ± 0.01 |      3.88 ± 0.01 |          -0.1 | ✅         |
| draco3        | 33 |           5e-14 | ✅       |    3.72 ± 0.01 |      3.72 ± 0.01 |          -0.1 | ✅         |
| ergocub       | 63 |           1e-14 | ✅       |    7.76 ± 0.03 |      7.64 ± 0.03 |          -1.6 | ✅         |
| h1            | 25 |           1e-14 | ✅       |    3.33 ± 0.01 |      3.35 ± 0.01 |          +0.6 | ✅         |
| icub          | 38 |           2e-13 | ✅       |    4.27 ± 0.01 |      4.20 ± 0.01 |          -1.7 | ✅         |
| jaxon         | 44 |           1e-13 | ✅       |    4.13 ± 0.01 |      4.11 ± 0.01 |          -0.6 | ✅         |
| jvrc          | 50 |           5e-13 | ✅       |    4.61 ± 0.02 |      4.58 ± 0.02 |          -0.5 | ✅         |
| r2            | 62 |           2e-14 | ✅       |    5.66 ± 0.02 |      5.61 ± 0.02 |          -0.9 | ✅         |
| romeo         | 67 |           5e-14 | ✅       |    5.08 ± 0.02 |      5.00 ± 0.02 |          -1.4 | ✅         |
| sigmaban      | 26 |           6e-14 | ✅       |    3.03 ± 0.01 |      3.05 ± 0.01 |          +0.6 | ✅         |
| talos         | 50 |           9e-12 | ✅       |    4.33 ± 0.02 |      4.30 ± 0.01 |          -0.6 | ✅         |
| valkyrie      | 65 |           4e-15 | ✅       |    5.44 ± 0.03 |      5.39 ± 0.03 |          -1.0 | ✅         |
| bolt          | 12 |           2e-15 | ✅       |    2.61 ± 0.01 |      2.65 ± 0.01 |          +1.8 | ✅         |
| cassie        | 22 |           3e-15 | ✅       |    3.34 ± 0.01 |      3.36 ± 0.01 |          +0.7 | ✅         |
| spryped       | 14 |           8e-15 | ✅       |    2.59 ± 0.01 |      2.63 ± 0.01 |          +1.7 | ✅         |

The data corresponding to this run is available in the `results/` directory.

<!-- END BENCHMARK RESULTS -->
