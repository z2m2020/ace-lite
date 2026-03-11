"""Config pack loader for tuned override bundles.

A config pack is an optional JSON file that contains a flat "overrides" mapping
of CLI-style parameter names to values (for example, "top_k_files",
"candidate_ranker", "repomap_signal_weights"). It is designed to be:

- deterministic (stable precedence and parsing)
- fail-open (invalid packs are ignored with a warning)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_PACK_SCHEMA_VERSION = "ace-lite-config-pack-v1"


@dataclass(frozen=True, slots=True)
class ConfigPackLoadResult:
    enabled: bool
    path: str
    reason: str
    overrides: dict[str, Any]
    warning: str | None
    schema_version: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "path": str(self.path),
            "reason": str(self.reason),
            "schema_version": str(self.schema_version),
            "name": str(self.name),
            "override_count": len(self.overrides),
            "warning": str(self.warning or ""),
        }


def load_config_pack(*, path: str | Path | None) -> ConfigPackLoadResult:
    configured = str(path or "").strip()
    if not configured:
        return ConfigPackLoadResult(
            enabled=False,
            path="",
            reason="not_provided",
            overrides={},
            warning=None,
            schema_version="",
            name="",
        )

    pack_path = Path(configured).expanduser()
    if not pack_path.exists() or not pack_path.is_file():
        return ConfigPackLoadResult(
            enabled=False,
            path=str(pack_path),
            reason="not_found",
            overrides={},
            warning=None,
            schema_version="",
            name="",
        )

    try:
        payload = json.loads(pack_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ConfigPackLoadResult(
            enabled=False,
            path=str(pack_path),
            reason="invalid_json",
            overrides={},
            warning=str(exc)[:240],
            schema_version="",
            name="",
        )

    if not isinstance(payload, dict):
        return ConfigPackLoadResult(
            enabled=False,
            path=str(pack_path),
            reason="invalid_payload",
            overrides={},
            warning="config_pack_payload_not_object",
            schema_version="",
            name="",
        )

    schema_version = str(payload.get("schema_version") or "").strip()
    if schema_version and schema_version != CONFIG_PACK_SCHEMA_VERSION:
        return ConfigPackLoadResult(
            enabled=False,
            path=str(pack_path),
            reason="schema_mismatch",
            overrides={},
            warning=f"expected:{CONFIG_PACK_SCHEMA_VERSION}",
            schema_version=schema_version,
            name=str(payload.get("name") or "").strip(),
        )

    overrides = payload.get("overrides", payload)
    if not isinstance(overrides, dict):
        return ConfigPackLoadResult(
            enabled=False,
            path=str(pack_path),
            reason="invalid_overrides",
            overrides={},
            warning="config_pack_overrides_not_object",
            schema_version=schema_version,
            name=str(payload.get("name") or "").strip(),
        )

    normalized_overrides: dict[str, Any] = {}
    for key, value in overrides.items():
        name = str(key or "").strip()
        if not name:
            continue
        normalized_overrides[name] = value

    return ConfigPackLoadResult(
        enabled=True,
        path=str(pack_path),
        reason="ok",
        overrides=normalized_overrides,
        warning=None,
        schema_version=schema_version or CONFIG_PACK_SCHEMA_VERSION,
        name=str(payload.get("name") or "").strip(),
    )


__all__ = ["CONFIG_PACK_SCHEMA_VERSION", "ConfigPackLoadResult", "load_config_pack"]

