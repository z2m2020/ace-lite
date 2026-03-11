from __future__ import annotations

from ace_lite.chunking.robust_signature import (
    ROBUST_SIGNATURE_LITE_VERSION,
    build_robust_signature_lite,
    summarize_robust_signature,
)


def test_build_robust_signature_lite_is_deterministic_under_input_order_changes() -> None:
    left = build_robust_signature_lite(
        path="src/auth.py",
        qualified_name="src.auth.validate_token",
        name="validate_token",
        kind="function",
        signature="def validate_token(raw_token: str, refresh_id: str) -> bool:",
        imports=[
            {"module": "src.core.token"},
            {"module": "typing", "name": "Optional"},
        ],
        references=[
            {"qualified_name": "src.core.token.parse_token", "name": "parse_token"},
            {"qualified_name": "src.session.refresh", "name": "refresh"},
        ],
    )
    right = build_robust_signature_lite(
        path="src/auth.py",
        qualified_name="src.auth.validate_token",
        name="validate_token",
        kind="function",
        signature="def validate_token(raw_token: str, refresh_id: str) -> bool:",
        imports=[
            {"module": "typing", "name": "Optional"},
            {"module": "src.core.token"},
        ],
        references=[
            {"qualified_name": "src.session.refresh", "name": "refresh"},
            {"qualified_name": "src.core.token.parse_token", "name": "parse_token"},
        ],
    )

    assert left == right
    assert left["available"] is True
    assert left["version"] == ROBUST_SIGNATURE_LITE_VERSION
    assert left["entity_vocab_count"] <= 12


def test_build_robust_signature_lite_caps_noise_and_preserves_shape_hash() -> None:
    baseline = build_robust_signature_lite(
        path="src/service.py",
        qualified_name="src.service.fetch_user_profile",
        name="fetch_user_profile",
        kind="function",
        signature="def fetch_user_profile(user_id: str, include_roles: bool = False) -> dict:",
        imports=[{"module": "src.repo.users"}],
        references=[{"qualified_name": "src.repo.users.fetch_user", "name": "fetch_user"}],
    )
    renamed = build_robust_signature_lite(
        path="src/service.py",
        qualified_name="src.service.load_user_profile",
        name="load_user_profile",
        kind="function",
        signature="def load_user_profile(profile_id: str, include_roles: bool = False) -> dict:",
        imports=[{"module": "src.repo.users"}],
        references=[
            {"qualified_name": "src.repo.users.fetch_user", "name": "fetch_user"},
            {"qualified_name": "tmp.DEBUG.noisy.NOISE", "name": "tmp"},
        ],
    )

    assert baseline["shape_hash"] == renamed["shape_hash"]
    assert renamed["entity_vocab_count"] <= 12
    assert "tmp" not in renamed["entity_vocab"]


def test_build_robust_signature_lite_fails_open_on_partial_metadata() -> None:
    signature = build_robust_signature_lite(
        path="",
        qualified_name="",
        name="",
        kind="function",
        signature="",
        imports=[],
        references=[],
    )
    summary = summarize_robust_signature(signature)

    assert signature["available"] is False
    assert signature["shape_hash"] == ""
    assert signature["entity_vocab"] == ()
    assert summary == {
        "version": ROBUST_SIGNATURE_LITE_VERSION,
        "available": False,
        "compatibility_domain": "",
        "shape_hash": "",
        "entity_vocab_count": 0,
    }
