"""Shared Pydantic helpers.

Keep small base-model conventions in one place to avoid copy/paste drift.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


__all__ = ["StrictModel"]

