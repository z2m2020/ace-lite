"""Shared helpers for benchmark summaries."""

from __future__ import annotations

import math

PIPELINE_STAGE_ORDER = (
    "memory",
    "index",
    "repomap",
    "augment",
    "skills",
    "source_plan",
)


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(item or 0.0) for item in values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


__all__ = ["PIPELINE_STAGE_ORDER", "p95"]
