from __future__ import annotations

from typing import Any

from ace_lite.pipeline.types import StageEvent


class HookBus:
    def __init__(self) -> None:
        self._before: list[tuple[str, Any]] = []
        self._after: list[tuple[str, Any]] = []

    def register_before(self, plugin_name: str, hook: Any) -> None:
        self._before.append((plugin_name, hook))

    def register_after(self, plugin_name: str, hook: Any) -> None:
        self._after.append((plugin_name, hook))

    def dispatch_before(self, event: StageEvent) -> list[str]:
        fired: list[str] = []
        for plugin_name, hook in self._before:
            if hook(event):
                fired.append(plugin_name)
        return fired

    def dispatch_after(
        self, event: StageEvent
    ) -> tuple[list[dict[str, Any]], list[str]]:
        contributions: list[dict[str, Any]] = []
        fired: list[str] = []
        for plugin_name, hook in self._after:
            result = hook(event)
            if not result:
                continue
            fired.append(plugin_name)
            contributions.extend(
                _normalize_after_result(plugin_name=plugin_name, result=result)
            )
        return contributions, fired


def _normalize_after_result(*, plugin_name: str, result: Any) -> list[dict[str, Any]]:
    if result is None or result is False:
        return []

    if isinstance(result, list):
        return _from_list(plugin_name=plugin_name, values=result)

    if isinstance(result, dict):
        if "slot" in result and "value" in result:
            contribution = _make_contribution(plugin_name=plugin_name, value=result)
            return [contribution] if contribution is not None else []

        slots = result.get("slots")
        if isinstance(slots, dict):
            return [
                {
                    "plugin": plugin_name,
                    "slot": str(slot),
                    "value": value,
                    "mode": "set",
                }
                for slot, value in slots.items()
                if str(slot).strip()
            ]
        if isinstance(slots, list):
            return _from_list(plugin_name=plugin_name, values=slots)

        flattened: list[dict[str, Any]] = []
        _flatten_dict_to_slots(
            plugin_name=plugin_name, source=result, prefix="", output=flattened
        )
        return flattened

    return []


def _from_list(*, plugin_name: str, values: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in values:
        contribution = _make_contribution(plugin_name=plugin_name, value=item)
        if contribution is None:
            continue
        normalized.append(contribution)
    return normalized


def _make_contribution(*, plugin_name: str, value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    slot = str(value.get("slot", "")).strip()
    if not slot:
        return None

    mode = str(value.get("mode", "set")).strip().lower()
    if mode not in {"set", "append"}:
        mode = "set"

    contribution: dict[str, Any] = {
        "plugin": plugin_name,
        "slot": slot,
        "value": value.get("value"),
        "mode": mode,
    }
    source = str(value.get("source", "")).strip()
    if source:
        contribution["source"] = source
    return contribution


def _flatten_dict_to_slots(
    *,
    plugin_name: str,
    source: dict[str, Any],
    prefix: str,
    output: list[dict[str, Any]],
) -> None:
    for key, value in source.items():
        name = str(key).strip()
        if not name:
            continue
        slot = f"{prefix}.{name}" if prefix else name
        if isinstance(value, dict):
            _flatten_dict_to_slots(
                plugin_name=plugin_name, source=value, prefix=slot, output=output
            )
            continue
        output.append(
            {
                "plugin": plugin_name,
                "slot": slot,
                "value": value,
                "mode": "set",
            }
        )


__all__ = ["HookBus"]
