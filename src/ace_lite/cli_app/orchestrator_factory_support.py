"""Shared canonical payload helpers for orchestrator factory wiring."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ace_lite.cli_app.orchestrator_factory_memory_payload import (
    build_memory_payload,
)
from ace_lite.cli_app.orchestrator_factory_misc_payloads import (
    build_cochange_payload,
    build_embeddings_payload,
    build_index_payload,
    build_lsp_payload,
    build_plan_replay_cache_payload,
    build_plugins_payload,
    build_repomap_payload,
    build_scip_payload,
    build_skills_payload,
    build_tests_payload,
    build_tokenizer_payload,
    build_trace_payload,
)
from ace_lite.cli_app.orchestrator_factory_payload_core import (
    CanonicalFieldSpec,
    build_canonical_payload,
    resolve_grouped_value,
)
from ace_lite.cli_app.orchestrator_factory_retrieval_payloads import (
    build_chunking_payload,
    build_retrieval_payload,
)
from ace_lite.cli_app.orchestrator_factory_run_plan_sections import (
    GroupedFlatSectionSpec,
    build_adaptive_router_run_plan_section_spec,
    build_chunking_run_plan_section_spec,
    build_memory_run_plan_section_spec,
    build_passthrough_run_plan_section_specs,
    build_retrieval_run_plan_section_spec,
    merge_group_or_flat_sections,
    normalize_group_mapping,
)


@dataclass(frozen=True)
class PayloadFamilyDescriptor:
    family: str
    builder: Callable[..., dict[str, Any]]
    grouped_inputs: tuple[str, ...]

def _build_payload_family_registry() -> dict[str, PayloadFamilyDescriptor]:
    descriptors = (
        PayloadFamilyDescriptor(
            family="memory",
            builder=build_memory_payload,
            grouped_inputs=("memory_group",),
        ),
        PayloadFamilyDescriptor(
            family="retrieval",
            builder=build_retrieval_payload,
            grouped_inputs=("retrieval_group", "adaptive_router_group"),
        ),
        PayloadFamilyDescriptor(
            family="chunking",
            builder=build_chunking_payload,
            grouped_inputs=("chunking_group",),
        ),
        PayloadFamilyDescriptor(
            family="skills",
            builder=build_skills_payload,
            grouped_inputs=("skills_group",),
        ),
        PayloadFamilyDescriptor(
            family="index",
            builder=build_index_payload,
            grouped_inputs=("index_group",),
        ),
        PayloadFamilyDescriptor(
            family="repomap",
            builder=build_repomap_payload,
            grouped_inputs=("repomap_group",),
        ),
        PayloadFamilyDescriptor(
            family="lsp",
            builder=build_lsp_payload,
            grouped_inputs=("lsp_group",),
        ),
        PayloadFamilyDescriptor(
            family="plugins",
            builder=build_plugins_payload,
            grouped_inputs=("plugins_group",),
        ),
        PayloadFamilyDescriptor(
            family="embeddings",
            builder=build_embeddings_payload,
            grouped_inputs=("embeddings_group",),
        ),
        PayloadFamilyDescriptor(
            family="tokenizer",
            builder=build_tokenizer_payload,
            grouped_inputs=("tokenizer_group",),
        ),
        PayloadFamilyDescriptor(
            family="cochange",
            builder=build_cochange_payload,
            grouped_inputs=("cochange_group",),
        ),
        PayloadFamilyDescriptor(
            family="trace",
            builder=build_trace_payload,
            grouped_inputs=("trace_group",),
        ),
        PayloadFamilyDescriptor(
            family="plan_replay_cache",
            builder=build_plan_replay_cache_payload,
            grouped_inputs=("plan_replay_cache_group",),
        ),
        PayloadFamilyDescriptor(
            family="tests",
            builder=build_tests_payload,
            grouped_inputs=("tests_group",),
        ),
        PayloadFamilyDescriptor(
            family="scip",
            builder=build_scip_payload,
            grouped_inputs=("scip_group",),
        ),
    )
    return {descriptor.family: descriptor for descriptor in descriptors}


PAYLOAD_FAMILY_REGISTRY: Mapping[str, PayloadFamilyDescriptor] = MappingProxyType(
    _build_payload_family_registry()
)


def iter_payload_family_descriptors() -> tuple[PayloadFamilyDescriptor, ...]:
    return tuple(PAYLOAD_FAMILY_REGISTRY.values())


def get_payload_family_descriptor(family: str) -> PayloadFamilyDescriptor:
    try:
        return PAYLOAD_FAMILY_REGISTRY[family]
    except KeyError as exc:
        raise KeyError(f"Unknown payload family: {family}") from exc


def build_payload_family(
    family: str,
    **kwargs: Any,
) -> dict[str, Any]:
    descriptor = get_payload_family_descriptor(family)
    return descriptor.builder(**kwargs)


__all__ = [
    "CanonicalFieldSpec",
    "GroupedFlatSectionSpec",
    "build_canonical_payload",
    "build_adaptive_router_run_plan_section_spec",
    "build_chunking_run_plan_section_spec",
    "build_chunking_payload",
    "build_cochange_payload",
    "build_embeddings_payload",
    "build_index_payload",
    "build_lsp_payload",
    "build_memory_run_plan_section_spec",
    "build_memory_payload",
    "build_passthrough_run_plan_section_specs",
    "build_plan_replay_cache_payload",
    "build_plugins_payload",
    "build_repomap_payload",
    "build_retrieval_run_plan_section_spec",
    "build_retrieval_payload",
    "build_scip_payload",
    "build_skills_payload",
    "build_tests_payload",
    "build_tokenizer_payload",
    "build_trace_payload",
    "merge_group_or_flat_sections",
    "normalize_group_mapping",
    "resolve_grouped_value",
]
