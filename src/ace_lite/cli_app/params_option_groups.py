"""Static CLI option groups and related choice/preset constants."""

from __future__ import annotations

from collections.abc import Callable
from types import MappingProxyType
from typing import Any

from ace_lite.cli_app.params_option_catalog import (
    ADAPTIVE_ROUTER_MODE_CHOICES,
    CANDIDATE_RANKER_CHOICES,
    CHUNK_DISCLOSURE_CHOICES,
    CHUNK_GUARD_MODE_CHOICES,
    EMBEDDING_PROVIDER_CHOICES,
    HYBRID_FUSION_CHOICES,
    MEMORY_AUTO_TAG_MODE_CHOICES,
    MEMORY_GATE_MODE_CHOICES,
    MEMORY_STRATEGY_CHOICES,
    REMOTE_SLOT_POLICY_CHOICES,
    RETRIEVAL_POLICY_CHOICES,
    RETRIEVAL_PRESET_CHOICES,
    RETRIEVAL_PRESETS,
    SBFL_METRIC_CHOICES,
    SCIP_PROVIDER_CHOICES,
)
from ace_lite.cli_app.params_option_core_groups import (
    SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS,
    SHARED_MEMORY_OPTION_DESCRIPTORS,
    SHARED_PLAN_REPLAY_OPTION_DESCRIPTORS,
    SHARED_SKILLS_OPTION_DESCRIPTORS,
    SHARED_TARGET_OPTION_DESCRIPTORS,
)
from ace_lite.cli_app.params_option_observability_groups import (
    SHARED_COCHANGE_OPTION_DESCRIPTORS,
    SHARED_LSP_OPTION_DESCRIPTORS,
    SHARED_POLICY_OPTION_DESCRIPTORS,
    SHARED_SCIP_OPTION_DESCRIPTORS,
    SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS,
    SHARED_TRACE_OPTION_DESCRIPTORS,
)
from ace_lite.cli_app.params_option_registry import (
    OptionDescriptor,
    OptionGroupDescriptor,
)
from ace_lite.cli_app.params_option_registry import (
    build_option_decorators as _build_option_decorators,
)
from ace_lite.cli_app.params_option_retrieval_groups import (
    SHARED_CANDIDATE_OPTION_DESCRIPTORS,
    SHARED_CHUNK_OPTION_DESCRIPTORS,
    SHARED_EMBEDDING_OPTION_DESCRIPTORS,
    SHARED_INDEX_OPTION_DESCRIPTORS,
    SHARED_REPOMAP_OPTION_DESCRIPTORS,
)


def _build_option_group_registry() -> dict[str, OptionGroupDescriptor]:
    descriptors = (
        OptionGroupDescriptor("memory", SHARED_MEMORY_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("skills", SHARED_SKILLS_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("target", SHARED_TARGET_OPTION_DESCRIPTORS),
        OptionGroupDescriptor(
            "adaptive_router",
            SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS,
        ),
        OptionGroupDescriptor("plan_replay", SHARED_PLAN_REPLAY_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("chunk", SHARED_CHUNK_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("candidate", SHARED_CANDIDATE_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("embedding", SHARED_EMBEDDING_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("index", SHARED_INDEX_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("lsp", SHARED_LSP_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("cochange", SHARED_COCHANGE_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("policy", SHARED_POLICY_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("repomap", SHARED_REPOMAP_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("test_signal", SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("scip", SHARED_SCIP_OPTION_DESCRIPTORS),
        OptionGroupDescriptor("trace", SHARED_TRACE_OPTION_DESCRIPTORS),
    )
    return {descriptor.name: descriptor for descriptor in descriptors}


OPTION_GROUP_REGISTRY = MappingProxyType(_build_option_group_registry())


def iter_option_group_descriptors() -> tuple[OptionGroupDescriptor, ...]:
    return tuple(OPTION_GROUP_REGISTRY.values())


def get_option_group_descriptor(name: str) -> OptionGroupDescriptor:
    try:
        return OPTION_GROUP_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown option group: {name}") from exc


def build_option_group_decorators(
    name: str,
) -> tuple[Callable[[Callable[..., Any]], Callable[..., Any]], ...]:
    return _build_option_decorators(get_option_group_descriptor(name).option_descriptors)


__all__ = [
    "ADAPTIVE_ROUTER_MODE_CHOICES",
    "CANDIDATE_RANKER_CHOICES",
    "CHUNK_DISCLOSURE_CHOICES",
    "CHUNK_GUARD_MODE_CHOICES",
    "EMBEDDING_PROVIDER_CHOICES",
    "HYBRID_FUSION_CHOICES",
    "MEMORY_AUTO_TAG_MODE_CHOICES",
    "MEMORY_GATE_MODE_CHOICES",
    "MEMORY_STRATEGY_CHOICES",
    "OPTION_GROUP_REGISTRY",
    "REMOTE_SLOT_POLICY_CHOICES",
    "RETRIEVAL_POLICY_CHOICES",
    "RETRIEVAL_PRESETS",
    "RETRIEVAL_PRESET_CHOICES",
    "SBFL_METRIC_CHOICES",
    "SCIP_PROVIDER_CHOICES",
    "SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS",
    "SHARED_CANDIDATE_OPTION_DESCRIPTORS",
    "SHARED_CHUNK_OPTION_DESCRIPTORS",
    "SHARED_COCHANGE_OPTION_DESCRIPTORS",
    "SHARED_EMBEDDING_OPTION_DESCRIPTORS",
    "SHARED_INDEX_OPTION_DESCRIPTORS",
    "SHARED_LSP_OPTION_DESCRIPTORS",
    "SHARED_MEMORY_OPTION_DESCRIPTORS",
    "SHARED_POLICY_OPTION_DESCRIPTORS",
    "SHARED_REPOMAP_OPTION_DESCRIPTORS",
    "SHARED_SCIP_OPTION_DESCRIPTORS",
    "SHARED_SKILLS_OPTION_DESCRIPTORS",
    "SHARED_TARGET_OPTION_DESCRIPTORS",
    "SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS",
    "SHARED_TRACE_OPTION_DESCRIPTORS",
    "OptionDescriptor",
    "OptionGroupDescriptor",
    "_build_option_decorators",
    "build_option_group_decorators",
    "get_option_group_descriptor",
    "iter_option_group_descriptors",
]
