"""CLI parameter parsing and coercion helpers."""

from __future__ import annotations

import shlex
from typing import Any

import click

from ace_lite.cli_app.params_option_groups import (
    ADAPTIVE_ROUTER_MODE_CHOICES,
    CANDIDATE_RANKER_CHOICES,
    CHUNK_DISCLOSURE_CHOICES,
    CHUNK_GUARD_MODE_CHOICES,
    EMBEDDING_PROVIDER_CHOICES,
    HYBRID_FUSION_CHOICES,
    MEMORY_AUTO_TAG_MODE_CHOICES,
    MEMORY_GATE_MODE_CHOICES,
    REMOTE_SLOT_POLICY_CHOICES,
    RETRIEVAL_POLICY_CHOICES,
    RETRIEVAL_PRESETS,
    SBFL_METRIC_CHOICES,
    SCIP_PROVIDER_CHOICES,
)


def parse_lsp_command_options(values: tuple[str, ...]) -> dict[str, list[str]]:
    commands: dict[str, list[str]] = {}
    for raw in values:
        item = str(raw).strip()
        if not item:
            continue
        if "=" not in item:
            raise click.BadParameter(
                f"Invalid --lsp-cmd '{item}'. Expected language=command"
            )

        language, command_raw = item.split("=", 1)
        language = language.strip().lower()
        command_raw = command_raw.strip()
        if not language or not command_raw:
            raise click.BadParameter(
                f"Invalid --lsp-cmd '{item}'. Expected language=command"
            )

        command = shlex.split(command_raw)
        if not command:
            raise click.BadParameter(
                f"Invalid --lsp-cmd '{item}'. Command cannot be empty"
            )

        commands[language] = command
    return commands


def parse_lsp_commands_from_config(value: Any) -> dict[str, list[str]]:
    if value is None:
        return {}

    if isinstance(value, dict):
        commands: dict[str, list[str]] = {}
        for language, command in value.items():
            lang = str(language).strip().lower()
            if not lang:
                continue

            if isinstance(command, str):
                parsed = shlex.split(command)
            elif isinstance(command, (list, tuple)):
                parsed = [str(item).strip() for item in command if str(item).strip()]
            else:
                parsed = [str(command).strip()] if str(command).strip() else []

            if parsed:
                commands[lang] = parsed
        return commands

    if isinstance(value, str):
        return parse_lsp_command_options((value,))

    if isinstance(value, (list, tuple)):
        return parse_lsp_command_options(tuple(str(item) for item in value))

    raise click.BadParameter(
        "Invalid config for lsp_cmds. Expected mapping/string/list."
    )


def _resolve_retrieval_preset(value: str) -> dict[str, Any] | None:
    normalized = str(value or "none").strip().lower()
    if not normalized or normalized == "none":
        return None

    preset = RETRIEVAL_PRESETS.get(normalized)
    if preset is None:
        choices = ", ".join(sorted(RETRIEVAL_PRESETS))
        raise click.BadParameter(
            f"Unsupported retrieval preset: {normalized}. Expected one of: {choices}."
        )

    resolved = dict(preset)
    weights = preset.get("repomap_signal_weights")
    if isinstance(weights, dict):
        resolved["repomap_signal_weights"] = dict(weights)
    return resolved


def _to_csv_languages(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ",".join(parts)
    return str(value)


def _to_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _to_slot_allowlist(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        normalized: list[str] = []
        for item in value:
            slot = str(item).strip()
            if slot and slot not in normalized:
                normalized.append(slot)
        return normalized
    slot = str(value).strip()
    return [slot] if slot else []


def _to_remote_slot_policy_mode(value: Any) -> str:
    if isinstance(value, bool):
        return "strict" if value else "off"
    normalized = str(value or "strict").strip().lower()
    if normalized not in REMOTE_SLOT_POLICY_CHOICES:
        choices = ", ".join(REMOTE_SLOT_POLICY_CHOICES)
        raise click.BadParameter(
            f"Unsupported remote slot policy mode: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise click.BadParameter(f"Unable to coerce boolean value from: {value}")


def _to_int(value: Any) -> int:
    return int(value)


def _to_float(value: Any) -> float:
    return float(value)


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _to_memory_auto_tag_mode(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized not in MEMORY_AUTO_TAG_MODE_CHOICES:
        choices = ", ".join(MEMORY_AUTO_TAG_MODE_CHOICES)
        raise click.BadParameter(
            f"Unsupported memory auto tag mode: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_memory_gate_mode(value: Any) -> str:
    normalized = str(value or "auto").strip().lower() or "auto"
    if normalized not in MEMORY_GATE_MODE_CHOICES:
        choices = ", ".join(MEMORY_GATE_MODE_CHOICES)
        raise click.BadParameter(
            f"Unsupported memory gate mode: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_candidate_ranker(value: Any) -> str:
    normalized = str(value or "heuristic").strip().lower()
    if normalized not in CANDIDATE_RANKER_CHOICES:
        choices = ", ".join(CANDIDATE_RANKER_CHOICES)
        raise click.BadParameter(
            f"Unsupported candidate ranker: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_hybrid_fusion_mode(value: Any) -> str:
    normalized = str(value or "linear").strip().lower()
    if normalized not in HYBRID_FUSION_CHOICES:
        choices = ", ".join(HYBRID_FUSION_CHOICES)
        raise click.BadParameter(
            f"Unsupported hybrid fusion mode: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_retrieval_policy(value: Any) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized not in RETRIEVAL_POLICY_CHOICES:
        choices = ", ".join(RETRIEVAL_POLICY_CHOICES)
        raise click.BadParameter(
            f"Unsupported retrieval policy: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_adaptive_router_mode(value: Any) -> str:
    normalized = str(value or "observe").strip().lower() or "observe"
    if normalized not in ADAPTIVE_ROUTER_MODE_CHOICES:
        choices = ", ".join(ADAPTIVE_ROUTER_MODE_CHOICES)
        raise click.BadParameter(
            f"Unsupported adaptive router mode: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_tokenizer_model(value: Any) -> str:
    return str(value).strip()


def _to_chunk_disclosure(value: Any) -> str:
    normalized = str(value or "refs").strip().lower()
    if normalized not in CHUNK_DISCLOSURE_CHOICES:
        choices = ", ".join(CHUNK_DISCLOSURE_CHOICES)
        raise click.BadParameter(
            f"Unsupported chunk disclosure: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_chunk_guard_mode(value: Any) -> str:
    normalized = str(value or "off").strip().lower() or "off"
    if normalized not in CHUNK_GUARD_MODE_CHOICES:
        choices = ", ".join(CHUNK_GUARD_MODE_CHOICES)
        raise click.BadParameter(
            f"Unsupported chunk guard mode: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_sbfl_metric(value: Any) -> str:
    normalized = str(value or "ochiai").strip().lower()
    if normalized not in SBFL_METRIC_CHOICES:
        choices = ", ".join(SBFL_METRIC_CHOICES)
        raise click.BadParameter(
            f"Unsupported SBFL metric: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_scip_provider(value: Any) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized not in SCIP_PROVIDER_CHOICES:
        choices = ", ".join(SCIP_PROVIDER_CHOICES)
        raise click.BadParameter(
            f"Unsupported scip provider: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_embedding_provider(value: Any) -> str:
    normalized = str(value or "hash").strip().lower()
    if normalized not in EMBEDDING_PROVIDER_CHOICES:
        choices = ", ".join(EMBEDDING_PROVIDER_CHOICES)
        raise click.BadParameter(
            f"Unsupported embedding provider: {normalized}. Expected one of: {choices}"
        )
    return normalized


def _to_float_dict(value: Any) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise click.BadParameter("Expected mapping for repomap signal weights")

    payload: dict[str, float] = {}
    for key, raw in value.items():
        name = str(key).strip()
        if not name:
            continue
        payload[name] = float(raw)
    return payload


__all__ = [
    "_resolve_retrieval_preset",
    "_to_adaptive_router_mode",
    "_to_bool",
    "_to_candidate_ranker",
    "_to_chunk_disclosure",
    "_to_chunk_guard_mode",
    "_to_csv_languages",
    "_to_embedding_provider",
    "_to_float",
    "_to_float_dict",
    "_to_hybrid_fusion_mode",
    "_to_int",
    "_to_memory_auto_tag_mode",
    "_to_memory_gate_mode",
    "_to_optional_str",
    "_to_remote_slot_policy_mode",
    "_to_retrieval_policy",
    "_to_sbfl_metric",
    "_to_scip_provider",
    "_to_slot_allowlist",
    "_to_string_list",
    "_to_tokenizer_model",
    "parse_lsp_command_options",
    "parse_lsp_commands_from_config",
]
