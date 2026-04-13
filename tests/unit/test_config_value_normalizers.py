from __future__ import annotations

import re

import pytest

from ace_lite.config_choices import (
    ADAPTIVE_ROUTER_MODE_CHOICES,
    MEMORY_GATE_MODE_CHOICES,
)
from ace_lite.config_value_normalizers import (
    normalize_choice_value,
    normalize_optional_choice_value,
    validate_choice_value,
)


def test_validate_choice_value_preserves_message_shape() -> None:
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Unsupported adaptive_router.mode: invalid. Expected one of: observe, shadow, enforce"
        ),
    ):
        validate_choice_value(
            "invalid",
            field_name="adaptive_router.mode",
            choices=ADAPTIVE_ROUTER_MODE_CHOICES,
        )


def test_normalize_choice_value_falls_back_to_default() -> None:
    assert (
        normalize_choice_value(
            "invalid",
            choices=MEMORY_GATE_MODE_CHOICES,
            default="auto",
        )
        == "auto"
    )
    assert (
        normalize_choice_value(
            " ALWAYS ",
            choices=MEMORY_GATE_MODE_CHOICES,
            default="auto",
        )
        == "always"
    )


def test_normalize_optional_choice_value_returns_none_for_unknown_or_empty() -> None:
    assert (
        normalize_optional_choice_value(
            " repo ",
            choices=("repo", "user", "global"),
        )
        == "repo"
    )
    assert (
        normalize_optional_choice_value(
            "invalid",
            choices=("repo", "user", "global"),
        )
        is None
    )
    assert normalize_optional_choice_value("", choices=("repo", "user", "global")) is None
