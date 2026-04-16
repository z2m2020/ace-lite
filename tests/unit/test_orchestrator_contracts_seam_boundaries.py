from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_orchestrator_contracts_text() -> str:
    return (REPO_ROOT / "src" / "ace_lite" / "orchestrator_contracts.py").read_text(
        encoding="utf-8"
    )


def test_orchestrator_contracts_imports_support_modules() -> None:
    text = _read_orchestrator_contracts_text()

    expected_tokens = (
        "from ace_lite.orchestrator_contracts_coercion import (",
        "coerce_mapping",
        "coerce_mapping_list",
        "get_bool",
        "get_dict",
        "get_float",
        "get_int",
        "get_list",
        "get_optional",
        "get_optional_dict",
        "get_optional_str",
        "get_required",
        "get_str",
        "get_typed",
        "from ace_lite.orchestrator_contracts_adapters import (",
        "PlanRequestAdapter",
        "PlanResponseAdapter",
        "StageStateAdapter",
    )
    for token in expected_tokens:
        assert token in text


def test_orchestrator_contracts_keeps_moved_helpers_out_of_facade() -> None:
    text = _read_orchestrator_contracts_text()

    forbidden_local_helpers = (
        "def get_optional(",
        "def get_required(",
        "def get_typed(",
        "def get_str(",
        "def get_int(",
        "def get_float(",
        "def get_bool(",
        "def get_optional_str(",
        "def get_optional_dict(",
        "def get_list(",
        "def get_dict(",
        "def coerce_mapping(",
        "def coerce_mapping_list(",
        "class PlanRequestAdapter",
        "class PlanResponseAdapter",
        "class StageStateAdapter",
    )
    for token in forbidden_local_helpers:
        assert token not in text
