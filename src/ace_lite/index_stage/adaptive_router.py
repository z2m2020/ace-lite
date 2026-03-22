"""Adaptive-router payload helpers for the index stage."""

from __future__ import annotations

from typing import Any


def build_adaptive_router_payload(
    *,
    enabled: bool,
    mode: str,
    model_path: str,
    state_path: str,
    arm_set: str,
    policy: dict[str, Any],
    shadow: dict[str, Any] | None = None,
    online_bandit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    router_enabled = bool(enabled)
    source = str(policy.get("source", "")).strip() if router_enabled else "disabled"
    confidence = 1.0 if router_enabled and source == "configured" else 0.0
    shadow_payload = shadow if isinstance(shadow, dict) else {}
    online_bandit_payload = online_bandit if isinstance(online_bandit, dict) else {}
    return {
        "enabled": router_enabled,
        "mode": str(mode).strip() or "observe",
        "model_path": str(model_path).strip(),
        "state_path": str(state_path).strip(),
        "arm_set": str(arm_set).strip() or "retrieval_policy_v1",
        "arm_id": str(policy.get("name", "")).strip() if router_enabled else "",
        "source": source,
        "confidence": float(confidence),
        "shadow_arm_id": (
            str(shadow_payload.get("arm_id", "")).strip() if router_enabled else ""
        ),
        "shadow_source": (
            str(shadow_payload.get("source", "")).strip() if router_enabled else ""
        ),
        "shadow_confidence": (
            float(shadow_payload.get("confidence", 0.0) or 0.0)
            if router_enabled
            else 0.0
        ),
        "online_bandit": dict(online_bandit_payload),
    }


__all__ = ["build_adaptive_router_payload"]
