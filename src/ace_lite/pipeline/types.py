from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


@dataclass(slots=True)
class StageContext:
    query: str
    repo: str
    root: str
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StageEvent:
    stage: str
    when: str
    context: StageContext
    payload: dict[str, Any]


@dataclass(slots=True)
class StagePatch:
    patch: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StageMetric:
    stage: str
    elapsed_ms: float
    plugins: list[str] = field(default_factory=list)
    tags: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StageDescriptor:
    name: str
    contract_enforced: bool = True


StageCallable = Callable[[StageContext], dict[str, Any]]


def run_stage(stage_name: str, func: StageCallable, ctx: StageContext) -> tuple[dict[str, Any], float]:
    started = perf_counter()
    payload = func(ctx)
    elapsed_ms = (perf_counter() - started) * 1000.0
    return payload, elapsed_ms


__all__ = [
    "StageCallable",
    "StageContext",
    "StageDescriptor",
    "StageEvent",
    "StageMetric",
    "StagePatch",
    "run_stage",
]
