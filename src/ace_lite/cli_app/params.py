"""Click option definitions and CLI parameter coercion helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import click

from ace_lite.cli_app.params_normalize import (
    _resolve_retrieval_preset,
    _to_adaptive_router_mode,
    _to_bool,
    _to_candidate_ranker,
    _to_chunk_disclosure,
    _to_chunk_guard_mode,
    _to_csv_languages,
    _to_embedding_provider,
    _to_float,
    _to_float_dict,
    _to_hybrid_fusion_mode,
    _to_int,
    _to_memory_auto_tag_mode,
    _to_memory_gate_mode,
    _to_optional_str,
    _to_remote_slot_policy_mode,
    _to_retrieval_policy,
    _to_sbfl_metric,
    _to_scip_provider,
    _to_slot_allowlist,
    _to_string_list,
    _to_tokenizer_model,
    parse_lsp_command_options,
    parse_lsp_commands_from_config,
)
from ace_lite.cli_app.params_option_groups import (
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
    RETRIEVAL_PRESETS,
    RETRIEVAL_PRESET_CHOICES,
    SBFL_METRIC_CHOICES,
    SCIP_PROVIDER_CHOICES,
    SHARED_CANDIDATE_OPTION_DESCRIPTORS,
    SHARED_CHUNK_OPTION_DESCRIPTORS,
    SHARED_COCHANGE_OPTION_DESCRIPTORS,
    SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS,
    SHARED_EMBEDDING_OPTION_DESCRIPTORS,
    SHARED_LSP_OPTION_DESCRIPTORS,
    SHARED_MEMORY_OPTION_DESCRIPTORS,
    SHARED_PLAN_REPLAY_OPTION_DESCRIPTORS,
    SHARED_SKILLS_OPTION_DESCRIPTORS,
    SHARED_POLICY_OPTION_DESCRIPTORS,
    SHARED_SCIP_OPTION_DESCRIPTORS,
    SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS,
    SHARED_TRACE_OPTION_DESCRIPTORS,
    _build_option_decorators,
)
from ace_lite.repomap.ranking import RANKING_PROFILES


def _apply_click_options(
    *options: Callable[[Callable[..., Any]], Callable[..., Any]],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        wrapped = func
        for option in reversed(options):
            wrapped = option(wrapped)
        return wrapped

    return _decorator


def _compose_click_decorators(
    *decorators: Callable[[Callable[..., Any]], Callable[..., Any]],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        wrapped = func
        for decorator in reversed(decorators):
            wrapped = decorator(wrapped)
        return wrapped

    return _decorator


def _with_shared_target_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        click.option("--repo", required=True, help="Repository identifier."),
        click.option(
            "--root",
            required=True,
            type=click.Path(path_type=str),
            help="Repository root path.",
        ),
        click.option(
            "--skills-dir",
            default="skills",
            show_default=True,
            type=click.Path(path_type=str),
            help="Markdown skills directory.",
        ),
        click.option(
            "--config-pack",
            default=None,
            envvar="ACE_LITE_CONFIG_PACK",
            show_default="env ACE_LITE_CONFIG_PACK",
            type=click.Path(path_type=str),
            help="Optional config pack JSON path to apply tuned overrides.",
        ),
        click.option(
            "--time-range",
            default=None,
            type=str,
            help="Optional time window for temporal filtering (e.g., 24h, 7d, 2w).",
        ),
        click.option(
            "--start-date",
            default=None,
            type=str,
            help="Optional ISO start date/datetime for temporal filtering (UTC unless configured).",
        ),
        click.option(
            "--end-date",
            default=None,
            type=str,
            help="Optional ISO end date/datetime for temporal filtering (UTC unless configured).",
        ),
    )(func)


def _with_shared_candidate_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_CANDIDATE_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_index_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        click.option(
            "--languages",
            default="python,typescript,javascript,go,markdown",
            show_default=True,
            help="Comma-separated index language profile.",
        ),
        click.option(
            "--index-cache-path",
            default="context-map/index.json",
            show_default=True,
            type=click.Path(path_type=str),
            help="Distilled index cache path.",
        ),
        click.option(
            "--index-incremental/--no-index-incremental",
            default=True,
            show_default=True,
            help="Enable incremental index refresh from git changed files.",
        ),
        click.option(
            "--conventions-file",
            "conventions_files",
            multiple=True,
            help="Convention file paths relative to --root.",
        ),
        click.option(
            "--plugins/--no-plugins",
            "plugins_enabled",
            default=True,
            show_default=True,
            help="Enable plugin loading from plugins/.",
        ),
        click.option(
            "--remote-slot-policy-mode",
            default="strict",
            show_default=True,
            type=click.Choice(list(REMOTE_SLOT_POLICY_CHOICES), case_sensitive=False),
            help="Policy mode for mcp_remote slot filtering: strict blocks, warn logs only, off disables filtering.",
        ),
        click.option(
            "--remote-slot-allowlist",
            default="observability.mcp_plugins",
            show_default=True,
            help="Comma-separated slot allowlist for mcp_remote contributions.",
        ),
    )(func)


def _with_shared_embedding_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_EMBEDDING_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_repomap_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        click.option(
            "--repomap/--no-repomap",
            "repomap_enabled",
            default=True,
            show_default=True,
            help="Enable repomap stage for one-hop dependency expansion.",
        ),
        click.option(
            "--repomap-top-k",
            default=8,
            show_default=True,
            type=int,
            help="Max seed files entering repomap stage.",
        ),
        click.option(
            "--repomap-neighbor-limit",
            default=20,
            show_default=True,
            type=int,
            help="Max one-hop neighbors collected by repomap stage.",
        ),
        click.option(
            "--repomap-budget-tokens",
            default=800,
            show_default=True,
            type=int,
            help="Token budget for repomap skeleton markdown.",
        ),
        click.option(
            "--repomap-ranking-profile",
            default="graph",
            show_default=True,
            type=click.Choice(list(RANKING_PROFILES), case_sensitive=False),
            help="Ranking profile used by repomap stage.",
        ),
        click.option(
            "--repomap-signal-weights",
            default=None,
            type=str,
            help="Optional JSON object for repomap signal weights.",
        ),
        click.option(
            "--verbose", is_flag=True, default=False, help="Enable debug logging."
        ),
    )(func)


def _with_shared_lsp_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_LSP_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_memory_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_MEMORY_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_skills_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_SKILLS_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_adaptive_router_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_plan_replay_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_PLAN_REPLAY_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_chunk_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_CHUNK_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_cochange_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_COCHANGE_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_policy_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_POLICY_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_test_signal_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_scip_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_SCIP_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_trace_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _apply_click_options(
        *_build_option_decorators(SHARED_TRACE_OPTION_DESCRIPTORS)
    )(func)


def _with_shared_plan_options(func: Callable[..., Any]) -> Callable[..., Any]:
    return _compose_click_decorators(
        _with_shared_target_options,
        _with_shared_candidate_options,
        _with_shared_index_options,
        _with_shared_embedding_options,
        _with_shared_repomap_options,
        _with_shared_lsp_options,
        _with_shared_memory_options,
        _with_shared_skills_options,
        _with_shared_adaptive_router_options,
        _with_shared_plan_replay_options,
        _with_shared_chunk_options,
        _with_shared_cochange_options,
        _with_shared_policy_options,
        _with_shared_test_signal_options,
        _with_shared_scip_options,
        _with_shared_trace_options,
    )(func)


__all__ = [
    "CANDIDATE_RANKER_CHOICES",
    "CHUNK_DISCLOSURE_CHOICES",
    "CHUNK_GUARD_MODE_CHOICES",
    "EMBEDDING_PROVIDER_CHOICES",
    "HYBRID_FUSION_CHOICES",
    "ADAPTIVE_ROUTER_MODE_CHOICES",
    "MEMORY_AUTO_TAG_MODE_CHOICES",
    "MEMORY_GATE_MODE_CHOICES",
    "MEMORY_STRATEGY_CHOICES",
    "REMOTE_SLOT_POLICY_CHOICES",
    "RETRIEVAL_POLICY_CHOICES",
    "RETRIEVAL_PRESETS",
    "RETRIEVAL_PRESET_CHOICES",
    "SBFL_METRIC_CHOICES",
    "SCIP_PROVIDER_CHOICES",
    "_resolve_retrieval_preset",
    "_to_bool",
    "_to_adaptive_router_mode",
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
    "_to_optional_str",
    "_to_remote_slot_policy_mode",
    "_to_retrieval_policy",
    "_to_sbfl_metric",
    "_to_scip_provider",
    "_to_slot_allowlist",
    "_to_string_list",
    "_to_tokenizer_model",
    "_with_shared_plan_options",
    "_with_shared_skills_options",
    "parse_lsp_command_options",
    "parse_lsp_commands_from_config",
]
