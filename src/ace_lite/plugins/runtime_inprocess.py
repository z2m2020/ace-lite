from __future__ import annotations

from ace_lite.pipeline.types import StageEvent


def before_stage(event: StageEvent) -> bool:
    return True


def after_stage(event: StageEvent) -> dict[str, object]:
    return {}


__all__ = ["after_stage", "before_stage"]
