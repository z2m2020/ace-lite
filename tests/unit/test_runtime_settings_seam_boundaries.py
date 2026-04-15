from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_runtime_settings_text() -> str:
    return (REPO_ROOT / "src" / "ace_lite" / "runtime_settings.py").read_text(
        encoding="utf-8"
    )


def test_runtime_settings_imports_projection_support() -> None:
    text = _read_runtime_settings_text()

    expected_tokens = (
        "from ace_lite.runtime_settings_projection import (",
        "_FieldSpec",
        "_build_payload_and_provenance",
        "_deep_merge",
        "_extract_path",
        "_normalize_mapping",
        "_spec",
    )
    for token in expected_tokens:
        assert token in text


def test_runtime_settings_keeps_projection_helpers_out_of_entry_module() -> None:
    text = _read_runtime_settings_text()

    assert "def _build_payload_and_provenance(" not in text
    assert "def _deep_merge(" not in text
    assert "def _normalize_mapping(" not in text
    assert "def _extract_path(" not in text
    assert "def _set_nested(" not in text
