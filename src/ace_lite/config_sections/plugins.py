from __future__ import annotations

from ace_lite.pydantic_utils import StrictModel as _StrictModel


class PluginsSectionSpec(_StrictModel):
    enabled: bool | None = None
    remote_slot_policy_mode: str | None = None
    remote_slot_allowlist: list[str] | tuple[str, ...] | str | None = None


__all__ = ["PluginsSectionSpec"]
