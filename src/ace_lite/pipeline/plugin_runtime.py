"""Plugin runtime helpers for orchestrator stage execution.

This module centralizes hook dispatch, slot contribution merging, and plugin
policy accounting so the orchestrator can remain a thin coordinator.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ace_lite.exceptions import StageContractError
from ace_lite.pipeline.contracts import validate_stage_output
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.types import StageContext, StageEvent, StageMetric, run_stage

logger = logging.getLogger(__name__)

DEFAULT_REMOTE_SLOT_ALLOWLIST: tuple[str, ...] = ("observability.mcp_plugins",)
REMOTE_SLOT_POLICY_MODES = ("strict", "warn", "off")

StageTagBuilder = Callable[..., dict[str, Any]]


def normalize_remote_slot_allowlist(
    allowlist: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    source = allowlist if allowlist is not None else DEFAULT_REMOTE_SLOT_ALLOWLIST
    normalized: list[str] = []
    for item in source:
        slot = str(item or "").strip()
        if slot and slot not in normalized:
            normalized.append(slot)
    return tuple(normalized)


def normalize_remote_slot_policy_mode(mode: str) -> str:
    normalized = str(mode or "strict").strip().lower() or "strict"
    if normalized not in REMOTE_SLOT_POLICY_MODES:
        return "strict"
    return normalized


def is_allowed_remote_slot(slot: str, *, allowlist: tuple[str, ...]) -> bool:
    normalized = str(slot or "").strip()
    if not normalized:
        return False
    return any(
        normalized == prefix or normalized.startswith(f"{prefix}.")
        for prefix in allowlist
    )


def _get_slot_value(payload: dict[str, Any], slot: str) -> Any | None:
    current: Any = payload
    for part in slot.split("."):
        key = part.strip()
        if not key:
            return None
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _set_slot_value(payload: dict[str, Any], slot: str, value: Any) -> None:
    parts = [part.strip() for part in slot.split(".") if part.strip()]
    if not parts:
        return

    current: dict[str, Any] = payload
    for part in parts[:-1]:
        existing = current.get(part)
        if not isinstance(existing, dict):
            existing = {}
            current[part] = existing
        current = existing
    current[parts[-1]] = value


def apply_slot_contributions(
    *,
    stage_name: str,
    output: dict[str, Any],
    contributions: list[dict[str, Any]],
    remote_slot_allowlist: tuple[str, ...],
    remote_slot_policy_mode: str,
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(output, dict) or not isinstance(contributions, list):
        return {"applied": [], "conflicts": []}

    allowlist = normalize_remote_slot_allowlist(remote_slot_allowlist)
    policy_mode = normalize_remote_slot_policy_mode(remote_slot_policy_mode)

    applied: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    winners: dict[str, dict[str, Any]] = {}

    for item in contributions:
        if not isinstance(item, dict):
            continue

        plugin = str(item.get("plugin", "")).strip() or "unknown"
        slot = str(item.get("slot", "")).strip()
        if not slot:
            continue

        relative_slot = slot
        prefix = f"{stage_name}."
        if relative_slot.startswith(prefix):
            relative_slot = relative_slot[len(prefix) :]
        if not relative_slot:
            continue

        source = str(item.get("source", "")).strip().lower()
        if (
            source == "mcp_remote"
            and policy_mode != "off"
            and not is_allowed_remote_slot(relative_slot, allowlist=allowlist)
        ):
            reason = "slot_not_allowed_for_source"
            if policy_mode == "warn":
                reason = "slot_not_allowed_for_source_warn"
            conflicts.append(
                {
                    "stage": stage_name,
                    "slot": relative_slot,
                    "mode": str(item.get("mode", "set")).strip().lower() or "set",
                    "winner_plugin": "slot_policy",
                    "discarded_plugin": plugin,
                    "reason": reason,
                    "source": source,
                }
            )
            if policy_mode == "strict":
                continue

        mode = str(item.get("mode", "set")).strip().lower()
        if mode == "append":
            previous = _get_slot_value(output, relative_slot)
            if previous is None:
                _set_slot_value(output, relative_slot, [])
                previous = _get_slot_value(output, relative_slot)

            if not isinstance(previous, list):
                conflicts.append(
                    {
                        "stage": stage_name,
                        "slot": relative_slot,
                        "mode": mode,
                        "winner_plugin": "existing_value",
                        "discarded_plugin": plugin,
                        "reason": "slot_not_list",
                        "source": source,
                    }
                )
                continue

            value = item.get("value")
            if isinstance(value, list):
                previous.extend(value)
                append_count = len(value)
            else:
                previous.append(value)
                append_count = 1

            applied.append(
                {
                    "stage": stage_name,
                    "plugin": plugin,
                    "slot": relative_slot,
                    "mode": "append",
                    "append_count": append_count,
                    "source": source,
                }
            )
            continue

        winner = winners.get(relative_slot)
        value = item.get("value")
        if winner is not None:
            if winner.get("value") != value:
                conflicts.append(
                    {
                        "stage": stage_name,
                        "slot": relative_slot,
                        "mode": "set",
                        "winner_plugin": winner.get("plugin"),
                        "discarded_plugin": plugin,
                        "source": source,
                    }
                )
            continue

        _set_slot_value(output, relative_slot, value)
        winners[relative_slot] = {
            "plugin": plugin,
            "value": value,
        }
        applied.append(
            {
                "stage": stage_name,
                "plugin": plugin,
                "slot": relative_slot,
                "mode": "set",
                "source": source,
            }
        )

    return {
        "applied": applied,
        "conflicts": conflicts,
    }


def summarize_slot_policy_events(
    *, slot_summary: dict[str, list[dict[str, Any]]]
) -> dict[str, int]:
    applied = slot_summary.get("applied") if isinstance(slot_summary, dict) else []
    conflicts = slot_summary.get("conflicts") if isinstance(slot_summary, dict) else []

    applied_rows = applied if isinstance(applied, list) else []
    conflict_rows = conflicts if isinstance(conflicts, list) else []

    blocked = 0
    warned = 0
    for item in conflict_rows:
        if not isinstance(item, dict):
            continue
        reason = str(item.get("reason", "")).strip().lower()
        if reason == "slot_not_allowed_for_source":
            blocked += 1
        elif reason == "slot_not_allowed_for_source_warn":
            warned += 1

    remote_applied = 0
    for item in applied_rows:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "")).strip().lower()
        if source == "mcp_remote":
            remote_applied += 1

    return {
        "applied": len(applied_rows),
        "conflicts": len(conflict_rows),
        "blocked": blocked,
        "warn": warned,
        "remote_applied": remote_applied,
    }


def build_plugin_policy_summary(
    *,
    stage_summary: dict[str, Any],
    pipeline_order: tuple[str, ...],
    remote_slot_allowlist: tuple[str, ...],
    remote_slot_policy_mode: str,
) -> dict[str, Any]:
    totals = {
        "applied": 0,
        "conflicts": 0,
        "blocked": 0,
        "warn": 0,
        "remote_applied": 0,
    }
    by_stage: list[dict[str, Any]] = []

    if isinstance(stage_summary, dict):
        for stage_name in pipeline_order:
            raw = stage_summary.get(stage_name)
            if not isinstance(raw, dict):
                continue

            normalized = {
                "applied": int(raw.get("applied", 0) or 0),
                "conflicts": int(raw.get("conflicts", 0) or 0),
                "blocked": int(raw.get("blocked", 0) or 0),
                "warn": int(raw.get("warn", 0) or 0),
                "remote_applied": int(raw.get("remote_applied", 0) or 0),
            }

            for key in totals:
                totals[key] += normalized[key]

            by_stage.append({"stage": stage_name, **normalized})

    return {
        "mode": normalize_remote_slot_policy_mode(remote_slot_policy_mode),
        "allowlist": list(normalize_remote_slot_allowlist(remote_slot_allowlist)),
        "totals": totals,
        "by_stage": by_stage,
    }


@dataclass(frozen=True, slots=True)
class PluginRuntimeConfig:
    remote_slot_allowlist: tuple[str, ...] = DEFAULT_REMOTE_SLOT_ALLOWLIST
    remote_slot_policy_mode: str = "strict"


class PluginRuntime:
    def __init__(self, *, config: PluginRuntimeConfig) -> None:
        self._remote_slot_allowlist = normalize_remote_slot_allowlist(
            config.remote_slot_allowlist
        )
        self._remote_slot_policy_mode = normalize_remote_slot_policy_mode(
            config.remote_slot_policy_mode
        )

    @property
    def remote_slot_allowlist(self) -> tuple[str, ...]:
        return self._remote_slot_allowlist

    @property
    def remote_slot_policy_mode(self) -> str:
        return self._remote_slot_policy_mode

    def execute_stage(
        self,
        *,
        stage_name: str,
        registry: StageRegistry,
        hook_bus: HookBus,
        ctx: StageContext,
        stage_metrics: list[StageMetric],
        tag_builder: StageTagBuilder,
    ) -> dict[str, Any]:
        before_event = StageEvent(stage=stage_name, when="before", context=ctx, payload={})
        before_plugins = hook_bus.dispatch_before(before_event)

        output, elapsed_ms = run_stage(
            stage_name, lambda stage_ctx: registry.run(stage_name, stage_ctx), ctx
        )

        after_event = StageEvent(stage=stage_name, when="after", context=ctx, payload=output)
        contributions, after_plugins = hook_bus.dispatch_after(after_event)

        slot_summary = apply_slot_contributions(
            stage_name=stage_name,
            output=output,
            contributions=contributions,
            remote_slot_allowlist=self._remote_slot_allowlist,
            remote_slot_policy_mode=self._remote_slot_policy_mode,
        )

        if slot_summary["applied"]:
            ctx.state.setdefault("_plugin_action_log", []).extend(slot_summary["applied"])
        if slot_summary["conflicts"]:
            ctx.state.setdefault("_plugin_conflicts", []).extend(slot_summary["conflicts"])

        policy_counts = summarize_slot_policy_events(slot_summary=slot_summary)
        policy_stage = ctx.state.setdefault("_plugin_policy_stage", {})
        if isinstance(policy_stage, dict):
            policy_stage[stage_name] = policy_counts

        contract_valid = True
        contract_error: StageContractError | None = None
        try:
            validate_stage_output(stage_name, output)
        except StageContractError as exc:
            contract_valid = False
            contract_error = exc
            ctx.state.setdefault("_contract_errors", []).append(
                {
                    "stage": stage_name,
                    "error_code": exc.error_code,
                    "reason": exc.reason,
                    "message": exc.message,
                    "context": exc.context,
                }
            )

        tags = tag_builder(stage_name=stage_name, output=output)
        if not isinstance(tags, dict):
            tags = {}
        tags["plugin_invocations"] = len(before_plugins) + len(after_plugins)
        tags["slot_contributions"] = len(slot_summary["applied"])
        tags["slot_conflicts"] = len(slot_summary["conflicts"])
        tags["slot_policy_blocked"] = policy_counts["blocked"]
        tags["slot_policy_warn"] = policy_counts["warn"]
        tags["slot_policy_remote_applied"] = policy_counts["remote_applied"]
        tags["contract_valid"] = contract_valid
        if contract_error is not None:
            tags["contract_error_code"] = contract_error.error_code
            tags["contract_reason"] = contract_error.reason

        stage_metrics.append(
            StageMetric(
                stage=stage_name,
                elapsed_ms=elapsed_ms,
                plugins=[*before_plugins, *after_plugins],
                tags=tags,
            )
        )

        logger.debug(
            "stage.metric",
            extra={
                "stage": stage_name,
                "elapsed_ms": round(elapsed_ms, 3),
                "plugin_invocations": tags.get("plugin_invocations", 0),
            },
        )
        if contract_error is not None:
            raise contract_error
        return output

    def build_policy_summary(
        self, *, stage_summary: dict[str, Any], pipeline_order: tuple[str, ...]
    ) -> dict[str, Any]:
        return build_plugin_policy_summary(
            stage_summary=stage_summary,
            pipeline_order=pipeline_order,
            remote_slot_allowlist=self._remote_slot_allowlist,
            remote_slot_policy_mode=self._remote_slot_policy_mode,
        )


__all__ = [
    "DEFAULT_REMOTE_SLOT_ALLOWLIST",
    "REMOTE_SLOT_POLICY_MODES",
    "PluginRuntime",
    "PluginRuntimeConfig",
    "apply_slot_contributions",
    "build_plugin_policy_summary",
    "is_allowed_remote_slot",
    "normalize_remote_slot_allowlist",
    "normalize_remote_slot_policy_mode",
    "summarize_slot_policy_events",
]
