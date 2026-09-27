# SPDX-License-Identifier: Apache-2.0

"""Compare Pinker against Pink over the pink_motions library of motions."""

import warnings

from pink_motions import SCENARIOS, Scenario
from qpsolvers.warnings import SparseConversionWarning

from .scene import Scene

# Pink and Pinker both hand qpsolvers dense QP matrices, which it converts to
# sparse ones for Clarabel. Both libraries pay that conversion, inside the same
# timed phase, so the warning is not relevant and disabled in the benchmark.
warnings.filterwarnings("ignore", category=SparseConversionWarning)

__version__ = "1.0.0"

__all__ = [
    "Scenario",
    "Scene",
    "SCENARIOS",
]
