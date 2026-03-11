from __future__ import annotations

from ace_lite.pipeline.types import StageEvent


def before_stage(event: StageEvent) -> bool:
    return event.stage == "source_plan"


def after_stage(event: StageEvent) -> dict[str, object]:
    if event.stage != "source_plan":
        return {}

    return {
        "writeback_template": {
            "decision": "Document final decision clearly.",
            "caveat": "Include rollback note if applicable.",
        }
    }
