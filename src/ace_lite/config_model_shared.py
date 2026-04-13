from __future__ import annotations

from typing import Literal

from ace_lite.chunking.disclosure_policy import CHUNK_DISCLOSURE_CHOICES
from ace_lite.config_choices import (
    ADAPTIVE_ROUTER_MODE_CHOICES,
    CHUNK_GUARD_MODE_CHOICES,
    EMBEDDING_PROVIDER_CHOICES,
    MEMORY_AUTO_TAG_MODE_CHOICES,
    MEMORY_GATE_MODE_CHOICES,
    MEMORY_NOTES_MODE_CHOICES,
    MEMORY_TIMEZONE_MODE_CHOICES,
    REMOTE_SLOT_POLICY_CHOICES,
    RETRIEVAL_POLICY_CHOICES,
    TOPOLOGICAL_SHIELD_MODE_CHOICES,
)
from ace_lite.config_value_normalizers import (
    normalize_choice_value,
    normalize_optional_choice_value,
    validate_choice_value,
)
from ace_lite.repomap.ranking import RANKING_PROFILES
from ace_lite.scip import SCIP_PROVIDERS
from ace_lite.scoring_config import (
    CANDIDATE_RANKER_CHOICES,
    HYBRID_FUSION_MODES,
    MEMORY_DISCLOSURE_MODES,
    MEMORY_STRATEGIES,
    SBFL_METRIC_CHOICES,
)

MemoryAutoTagMode = Literal["repo", "user", "global"]
MemoryTimezoneMode = Literal["utc", "local", "explicit"]
MemoryGateMode = Literal["auto", "always", "never"]
AdaptiveRouterMode = Literal["observe", "shadow", "enforce"]
ChunkGuardMode = Literal["off", "report_only", "enforce"]
TopologicalShieldMode = Literal["off", "report_only", "enforce"]
MemoryNotesMode = Literal["supplement", "prefer_local", "local_only"]


def normalize_memory_disclosure_mode(value: object, *, default: str = "compact") -> str:
    return normalize_choice_value(
        value,
        choices=MEMORY_DISCLOSURE_MODES,
        default=default,
    )


def validate_memory_disclosure_mode(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=MEMORY_DISCLOSURE_MODES,
    )


def normalize_memory_strategy(value: object, *, default: str = "hybrid") -> str:
    return normalize_choice_value(
        value,
        choices=MEMORY_STRATEGIES,
        default=default,
    )


def validate_memory_strategy(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=MEMORY_STRATEGIES,
    )


def normalize_chunk_disclosure(value: object, *, default: str = "refs") -> str:
    return normalize_choice_value(
        value,
        choices=CHUNK_DISCLOSURE_CHOICES,
        default=default,
    )


def validate_chunk_disclosure(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=CHUNK_DISCLOSURE_CHOICES,
    )


def normalize_candidate_ranker(value: object, *, default: str = "heuristic") -> str:
    return normalize_choice_value(
        value,
        choices=CANDIDATE_RANKER_CHOICES,
        default=default,
    )


def validate_candidate_ranker(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=CANDIDATE_RANKER_CHOICES,
    )


def validate_hybrid_fusion_mode(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=HYBRID_FUSION_MODES,
    )


def validate_ranking_profile(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=tuple(sorted(RANKING_PROFILES)),
    )


def validate_sbfl_metric(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=SBFL_METRIC_CHOICES,
    )


def validate_scip_provider(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=tuple(sorted(SCIP_PROVIDERS)),
    )


def validate_embedding_provider(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=EMBEDDING_PROVIDER_CHOICES,
    )


def normalize_ranking_profile(value: object, *, default: str = "graph") -> str:
    return normalize_choice_value(
        value,
        choices=tuple(sorted(RANKING_PROFILES)),
        default=default,
    )


def normalize_embedding_provider(value: object, *, default: str = "hash") -> str:
    return normalize_choice_value(
        value,
        choices=EMBEDDING_PROVIDER_CHOICES,
        default=default,
    )


def normalize_retrieval_policy(value: object, *, default: str = "auto") -> str:
    return normalize_choice_value(
        value,
        choices=RETRIEVAL_POLICY_CHOICES,
        default=default,
    )


def validate_retrieval_policy(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=RETRIEVAL_POLICY_CHOICES,
    )


def validate_remote_slot_policy_mode(
    value: str | None,
    *,
    field_name: str,
) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=REMOTE_SLOT_POLICY_CHOICES,
    )


def normalize_memory_auto_tag_mode(value: object) -> str | None:
    return normalize_optional_choice_value(
        value,
        choices=MEMORY_AUTO_TAG_MODE_CHOICES,
    )


def validate_memory_auto_tag_mode(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=MEMORY_AUTO_TAG_MODE_CHOICES,
    )


def normalize_memory_timezone_mode(value: object, *, default: str = "utc") -> str:
    return normalize_choice_value(
        value,
        choices=MEMORY_TIMEZONE_MODE_CHOICES,
        default=default,
    )


def validate_memory_timezone_mode(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=MEMORY_TIMEZONE_MODE_CHOICES,
    )


def normalize_memory_gate_mode(value: object, *, default: str = "auto") -> str:
    return normalize_choice_value(
        value,
        choices=MEMORY_GATE_MODE_CHOICES,
        default=default,
    )


def validate_memory_gate_mode(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=MEMORY_GATE_MODE_CHOICES,
    )


def normalize_memory_notes_mode(value: object, *, default: str = "supplement") -> str:
    return normalize_choice_value(
        value,
        choices=MEMORY_NOTES_MODE_CHOICES,
        default=default,
    )


def validate_memory_notes_mode(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=MEMORY_NOTES_MODE_CHOICES,
    )


def normalize_adaptive_router_mode(value: object, *, default: str = "observe") -> str:
    return normalize_choice_value(
        value,
        choices=ADAPTIVE_ROUTER_MODE_CHOICES,
        default=default,
    )


def validate_adaptive_router_mode(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=ADAPTIVE_ROUTER_MODE_CHOICES,
    )


def normalize_chunk_guard_mode(value: object, *, default: str = "off") -> str:
    return normalize_choice_value(
        value,
        choices=CHUNK_GUARD_MODE_CHOICES,
        default=default,
    )


def validate_chunk_guard_mode(value: str | None, *, field_name: str) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=CHUNK_GUARD_MODE_CHOICES,
    )


def normalize_topological_shield_mode(value: object, *, default: str = "off") -> str:
    return normalize_choice_value(
        value,
        choices=TOPOLOGICAL_SHIELD_MODE_CHOICES,
        default=default,
    )


def validate_topological_shield_mode(
    value: str | None,
    *,
    field_name: str,
) -> str | None:
    return validate_choice_value(
        value,
        field_name=field_name,
        choices=TOPOLOGICAL_SHIELD_MODE_CHOICES,
    )


__all__ = [
    "AdaptiveRouterMode",
    "ChunkGuardMode",
    "MemoryAutoTagMode",
    "MemoryGateMode",
    "MemoryNotesMode",
    "MemoryTimezoneMode",
    "TopologicalShieldMode",
    "normalize_adaptive_router_mode",
    "normalize_candidate_ranker",
    "normalize_chunk_disclosure",
    "normalize_chunk_guard_mode",
    "normalize_embedding_provider",
    "normalize_memory_auto_tag_mode",
    "normalize_memory_disclosure_mode",
    "normalize_memory_gate_mode",
    "normalize_memory_notes_mode",
    "normalize_memory_strategy",
    "normalize_memory_timezone_mode",
    "normalize_ranking_profile",
    "normalize_retrieval_policy",
    "normalize_topological_shield_mode",
    "validate_adaptive_router_mode",
    "validate_candidate_ranker",
    "validate_chunk_disclosure",
    "validate_chunk_guard_mode",
    "validate_embedding_provider",
    "validate_hybrid_fusion_mode",
    "validate_memory_auto_tag_mode",
    "validate_memory_disclosure_mode",
    "validate_memory_gate_mode",
    "validate_memory_notes_mode",
    "validate_memory_strategy",
    "validate_memory_timezone_mode",
    "validate_ranking_profile",
    "validate_remote_slot_policy_mode",
    "validate_retrieval_policy",
    "validate_sbfl_metric",
    "validate_scip_provider",
    "validate_topological_shield_mode",
]
