from __future__ import annotations

from ace_lite.index_stage.adaptive_router import build_adaptive_router_payload


def test_build_adaptive_router_payload_uses_defaults_and_configured_confidence() -> None:
    payload = build_adaptive_router_payload(
        enabled=True,
        mode=" ",
        model_path="context-map/router/model.json",
        state_path="context-map/router/state.json",
        arm_set=" ",
        policy={"name": "general", "source": "configured"},
        shadow={"arm_id": "shadow_arm", "confidence": 0.25},
        online_bandit={"requested": True},
    )

    assert payload == {
        "enabled": True,
        "mode": "observe",
        "model_path": "context-map/router/model.json",
        "state_path": "context-map/router/state.json",
        "arm_set": "retrieval_policy_v1",
        "arm_id": "general",
        "source": "configured",
        "confidence": 1.0,
        "shadow_arm_id": "shadow_arm",
        "shadow_confidence": 0.25,
        "online_bandit": {"requested": True},
    }


def test_build_adaptive_router_payload_disables_arm_fields_when_router_disabled() -> None:
    payload = build_adaptive_router_payload(
        enabled=False,
        mode="shadow",
        model_path="m.json",
        state_path="s.json",
        arm_set="retrieval_policy_shadow",
        policy={"name": "feature", "source": "auto"},
        shadow={"arm_id": "shadow_arm", "confidence": 0.75},
        online_bandit={"requested": False},
    )

    assert payload["enabled"] is False
    assert payload["arm_id"] == ""
    assert payload["source"] == "disabled"
    assert payload["confidence"] == 0.0
    assert payload["shadow_arm_id"] == ""
    assert payload["shadow_confidence"] == 0.0
    assert payload["online_bandit"] == {"requested": False}
