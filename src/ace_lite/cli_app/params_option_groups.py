"""Static CLI option groups and related choice/preset constants."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import click

from ace_lite.chunking.disclosure_policy import CHUNK_DISCLOSURE_CHOICES
from ace_lite.config_choices import (
    ADAPTIVE_ROUTER_MODE_CHOICES,
    CHUNK_GUARD_MODE_CHOICES,
    EMBEDDING_PROVIDER_CHOICES,
    MEMORY_AUTO_TAG_MODE_CHOICES,
    MEMORY_GATE_MODE_CHOICES,
    REMOTE_SLOT_POLICY_CHOICES,
    RETRIEVAL_POLICY_CHOICES,
)
from ace_lite.repomap.ranking import RANKING_PROFILES
from ace_lite.scip import SCIP_PROVIDERS

CANDIDATE_RANKER_CHOICES = ("heuristic", "bm25_lite", "hybrid_re2", "rrf_hybrid")
HYBRID_FUSION_CHOICES = ("linear", "rrf")
MEMORY_STRATEGY_CHOICES = ("semantic", "hybrid")
SBFL_METRIC_CHOICES = ("ochiai", "dstar")
SCIP_PROVIDER_CHOICES = tuple(SCIP_PROVIDERS)


RETRIEVAL_PRESETS: dict[str, dict[str, Any]] = {
    "balanced-v1": {
        "top_k_files": 6,
        "min_candidate_score": 2,
        "candidate_relative_threshold": 0.35,
        "candidate_ranker": "hybrid_re2",
        "repomap_signal_weights": {"base": 0.7, "graph": 0.25, "import_depth": 0.05},
    },
    "precision-v1": {
        "top_k_files": 4,
        "min_candidate_score": 2,
        "candidate_relative_threshold": 0.55,
        "candidate_ranker": "heuristic",
        "repomap_signal_weights": {"base": 0.75, "graph": 0.2, "import_depth": 0.05},
    },
    "recall-v1": {
        "top_k_files": 8,
        "min_candidate_score": 1,
        "candidate_relative_threshold": 0.0,
        "candidate_ranker": "hybrid_re2",
        "repomap_signal_weights": {"base": 0.6, "graph": 0.3, "import_depth": 0.1},
    },
}

RETRIEVAL_PRESET_CHOICES = ("none", *tuple(RETRIEVAL_PRESETS.keys()))
OptionDescriptor = tuple[tuple[str, ...], dict[str, Any]]


def _build_option_decorators(
    descriptors: tuple[OptionDescriptor, ...],
) -> tuple[Callable[[Callable[..., Any]], Callable[..., Any]], ...]:
    return tuple(
        click.option(*option_names, **option_kwargs)
        for option_names, option_kwargs in descriptors
    )


SHARED_MEMORY_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--memory-primary",),
        {
            "default": "mcp",
            "show_default": True,
            "type": click.Choice(["mcp", "rest", "none"], case_sensitive=False),
            "help": "Primary memory channel.",
        },
    ),
    (
        ("--memory-secondary",),
        {
            "default": "rest",
            "show_default": True,
            "type": click.Choice(["rest", "mcp", "none"], case_sensitive=False),
            "help": "Secondary memory channel.",
        },
    ),
    (
        ("--memory-strategy",),
        {
            "default": "hybrid",
            "show_default": True,
            "type": click.Choice(list(MEMORY_STRATEGY_CHOICES), case_sensitive=False),
            "help": "Memory retrieval strategy.",
        },
    ),
    (
        ("--memory-hybrid-limit",),
        {
            "default": 20,
            "show_default": True,
            "type": int,
            "help": "Top-k cap for hybrid memory merge.",
        },
    ),
    (
        ("--memory-cache/--no-memory-cache", "memory_cache_enabled"),
        {
            "default": True,
            "show_default": True,
            "help": "Enable local write-through memory cache.",
        },
    ),
    (
        ("--memory-cache-path",),
        {
            "default": "context-map/memory_cache.jsonl",
            "show_default": True,
            "type": click.Path(path_type=str),
            "help": "JSONL cache path for local memory cache.",
        },
    ),
    (
        ("--memory-cache-ttl-seconds",),
        {
            "default": 604800,
            "show_default": True,
            "type": int,
            "help": "TTL for local cache entries.",
        },
    ),
    (
        ("--memory-cache-max-entries",),
        {
            "default": 5000,
            "show_default": True,
            "type": int,
            "help": "Max local cache entries.",
        },
    ),
    (
        ("--memory-timeline/--no-memory-timeline", "memory_timeline_enabled"),
        {
            "default": True,
            "show_default": True,
            "help": "Enable timeline aggregation for memory previews.",
        },
    ),
    (
        ("--memory-container-tag",),
        {
            "default": None,
            "show_default": "(disabled)",
            "help": "Optional memory namespace tag (prevents cross-project memory mixing).",
        },
    ),
    (
        ("--memory-auto-tag-mode",),
        {
            "default": None,
            "show_default": "(disabled)",
            "type": click.Choice(list(MEMORY_AUTO_TAG_MODE_CHOICES), case_sensitive=False),
            "help": "Auto-generate memory container tag (repo/user/global). Enables namespace isolation when set.",
        },
    ),
    (
        ("--mcp-base-url",),
        {
            "default": lambda: os.getenv("ACE_LITE_MCP_BASE_URL", "http://localhost:8765"),
            "show_default": "env ACE_LITE_MCP_BASE_URL or http://localhost:8765",
            "help": "MCP bridge base URL.",
        },
    ),
    (
        ("--rest-base-url",),
        {
            "default": lambda: os.getenv("ACE_LITE_REST_BASE_URL", "http://localhost:8765"),
            "show_default": "env ACE_LITE_REST_BASE_URL or http://localhost:8765",
            "help": "REST base URL.",
        },
    ),
    (
        ("--memory-timeout",),
        {
            "default": 3.0,
            "show_default": True,
            "type": float,
            "help": "Network timeout seconds for memory calls.",
        },
    ),
    (
        ("--user-id",),
        {
            "default": lambda: os.getenv("ACE_LITE_USER_ID"),
            "help": "Optional memory user id.",
        },
    ),
    (
        ("--app",),
        {
            "default": lambda: os.getenv("ACE_LITE_APP", "codex"),
            "show_default": "env ACE_LITE_APP or codex",
            "help": "Memory app scope.",
        },
    ),
    (
        ("--memory-limit",),
        {
            "default": 8,
            "show_default": True,
            "type": int,
            "help": "Top-k memory retrieval depth.",
        },
    ),
    (
        ("--memory-disclosure", "memory_disclosure_mode"),
        {
            "default": "compact",
            "show_default": True,
            "type": click.Choice(["compact", "full"], case_sensitive=False),
            "help": "Memory disclosure mode (compact previews or full text).",
        },
    ),
    (
        ("--memory-preview-max-chars",),
        {
            "default": 280,
            "show_default": True,
            "type": int,
            "help": "Max characters kept per memory preview hit.",
        },
    ),
)


SHARED_SKILLS_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--precomputed-skills-routing/--no-precomputed-skills-routing", "precomputed_skills_routing_enabled"),
        {
            "default": True,
            "show_default": True,
            "help": "Precompute skill routing before the skills stage and reuse it during skill hydration.",
        },
    ),
)


SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--adaptive-router/--no-adaptive-router", "adaptive_router_enabled"),
        {
            "default": False,
            "show_default": True,
            "help": "Enable adaptive retrieval router observability metadata.",
        },
    ),
    (
        ("--adaptive-router-mode",),
        {
            "default": "observe",
            "show_default": True,
            "type": click.Choice(list(ADAPTIVE_ROUTER_MODE_CHOICES), case_sensitive=False),
            "help": "Adaptive router execution mode.",
        },
    ),
    (
        ("--adaptive-router-model-path",),
        {
            "default": "context-map/router/model.json",
            "show_default": True,
            "type": click.Path(path_type=str),
            "help": "Adaptive router model/catalog path for observability metadata.",
        },
    ),
    (
        ("--adaptive-router-state-path",),
        {
            "default": "context-map/router/state.json",
            "show_default": True,
            "type": click.Path(path_type=str),
            "help": "Adaptive router state path for observability metadata.",
        },
    ),
    (
        ("--adaptive-router-arm-set",),
        {
            "default": "retrieval_policy_v1",
            "show_default": True,
            "type": str,
            "help": "Adaptive router arm-set identifier exposed in payloads and traces.",
        },
    ),
)


SHARED_PLAN_REPLAY_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        (
            "--plan-replay-cache/--no-plan-replay-cache",
            "plan_replay_cache_enabled",
        ),
        {
            "default": False,
            "show_default": True,
            "help": "Replay exact cached late-stage plan sections when query, repo, policy, and budget inputs match.",
        },
    ),
    (
        ("--plan-replay-cache-path",),
        {
            "default": "context-map/plan-replay/cache.json",
            "show_default": True,
            "type": str,
            "help": "File path for the exact plan replay cache store.",
        },
    ),
)


SHARED_CHUNK_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--chunk-top-k",),
        {
            "default": 24,
            "show_default": True,
            "type": int,
            "help": "Top chunk candidates emitted by index stage.",
        },
    ),
    (
        ("--chunk-per-file-limit",),
        {
            "default": 3,
            "show_default": True,
            "type": int,
            "help": "Max chunk references emitted per file.",
        },
    ),
    (
        ("--chunk-disclosure",),
        {
            "default": "refs",
            "show_default": True,
            "type": click.Choice(list(CHUNK_DISCLOSURE_CHOICES), case_sensitive=False),
            "help": "Chunk disclosure mode: refs (metadata only), signature, or snippet.",
        },
    ),
    (
        ("--chunk-signature/--no-chunk-signature",),
        {
            "default": False,
            "show_default": True,
            "help": "Legacy alias for --chunk-disclosure=signature.",
        },
    ),
    (
        ("--chunk-snippet-max-lines",),
        {
            "default": 18,
            "show_default": True,
            "type": int,
            "help": "Max lines per chunk snippet (when --chunk-disclosure=snippet).",
        },
    ),
    (
        ("--chunk-snippet-max-chars",),
        {
            "default": 1200,
            "show_default": True,
            "type": int,
            "help": "Max characters per chunk snippet (when --chunk-disclosure=snippet).",
        },
    ),
    (
        ("--chunk-token-budget",),
        {
            "default": 1200,
            "show_default": True,
            "type": int,
            "help": "Estimated token budget for candidate chunks.",
        },
    ),
    (
        ("--chunk-guard/--no-chunk-guard", "chunk_guard_enabled"),
        {
            "default": False,
            "show_default": True,
            "help": "Enable chunk-guard evaluation; pair with --chunk-guard-mode report_only or enforce.",
        },
    ),
    (
        ("--chunk-guard-mode",),
        {
            "default": "off",
            "show_default": True,
            "type": click.Choice(list(CHUNK_GUARD_MODE_CHOICES), case_sensitive=False),
            "help": "Chunk-guard execution mode.",
        },
    ),
    (
        ("--chunk-guard-lambda-penalty",),
        {
            "default": 0.8,
            "show_default": True,
            "type": float,
            "help": "Penalty scale reserved for chunk-guard coherent-subset scoring.",
        },
    ),
    (
        ("--chunk-guard-min-pool",),
        {
            "default": 4,
            "show_default": True,
            "type": int,
            "help": "Minimum chunk pool size before chunk-guard evaluation activates.",
        },
    ),
    (
        ("--chunk-guard-max-pool",),
        {
            "default": 32,
            "show_default": True,
            "type": int,
            "help": "Maximum chunk pool size considered by chunk-guard evaluation.",
        },
    ),
    (
        ("--chunk-guard-min-marginal-utility",),
        {
            "default": 0.0,
            "show_default": True,
            "type": float,
            "help": "Reserved marginal-utility floor for chunk-guard filtering.",
        },
    ),
    (
        ("--chunk-guard-compatibility-min-overlap",),
        {
            "default": 0.3,
            "show_default": True,
            "type": float,
            "help": "Compatibility overlap floor used by chunk-guard conflict scoring.",
        },
    ),
    (
        ("--chunk-diversity-enabled/--no-chunk-diversity-enabled",),
        {
            "default": True,
            "show_default": True,
            "help": "Enable diversity-aware chunk selection.",
        },
    ),
    (
        ("--chunk-diversity-path-penalty",),
        {
            "default": 0.20,
            "show_default": True,
            "type": float,
            "help": "Penalty for selecting multiple chunks from the same file.",
        },
    ),
    (
        ("--chunk-diversity-symbol-family-penalty",),
        {
            "default": 0.30,
            "show_default": True,
            "type": float,
            "help": "Penalty for selecting repeated symbol-family chunks.",
        },
    ),
    (
        ("--chunk-diversity-kind-penalty",),
        {
            "default": 0.10,
            "show_default": True,
            "type": float,
            "help": "Penalty for selecting repeated chunk kinds.",
        },
    ),
    (
        ("--chunk-diversity-locality-penalty",),
        {
            "default": 0.15,
            "show_default": True,
            "type": float,
            "help": "Penalty for selecting nearby chunks in the same file.",
        },
    ),
    (
        ("--chunk-diversity-locality-window",),
        {
            "default": 24,
            "show_default": True,
            "type": int,
            "help": "Line window for locality diversity penalty.",
        },
    ),
    (
        ("--tokenizer-model",),
        {
            "default": "gpt-4o-mini",
            "show_default": True,
            "help": "Tokenizer model name used for token cost estimation.",
        },
    ),
)


SHARED_CANDIDATE_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--retrieval-preset",),
        {
            "default": "none",
            "show_default": True,
            "type": click.Choice(list(RETRIEVAL_PRESET_CHOICES), case_sensitive=False),
            "help": "Named retrieval preset overriding candidate/repomap tuning (explicit flags win).",
        },
    ),
    (
        ("--top-k-files",),
        {
            "default": 8,
            "show_default": True,
            "type": int,
            "help": "Top ranked candidate files to keep.",
        },
    ),
    (
        ("--min-candidate-score",),
        {
            "default": 2,
            "show_default": True,
            "type": int,
            "help": "Minimum candidate score to keep.",
        },
    ),
    (
        ("--candidate-relative-threshold",),
        {
            "default": 0.0,
            "show_default": True,
            "type": float,
            "help": "Keep only candidates scoring within this fraction of the best score (0 disables).",
        },
    ),
    (
        ("--candidate-ranker",),
        {
            "default": "rrf_hybrid",
            "show_default": True,
            "type": click.Choice(list(CANDIDATE_RANKER_CHOICES), case_sensitive=False),
            "help": "Candidate ranker profile for index-stage retrieval.",
        },
    ),
    (
        ("--exact-search/--no-exact-search",),
        {
            "default": False,
            "show_default": True,
            "help": "Optional ripgrep-powered exact search boost (feature flag).",
        },
    ),
    (
        ("--deterministic-refine/--no-deterministic-refine", "deterministic_refine_enabled"),
        {
            "default": True,
            "show_default": True,
            "help": "Enable the bounded deterministic refine retry for low-candidate retrieval.",
        },
    ),
    (
        ("--exact-search-time-budget-ms",),
        {
            "default": 40,
            "show_default": True,
            "type": int,
            "help": "Time budget for exact search (0 disables).",
        },
    ),
    (
        ("--exact-search-max-paths",),
        {
            "default": 24,
            "show_default": True,
            "type": int,
            "help": "Max files to inject/boost from exact search hits.",
        },
    ),
    (
        ("--hybrid-re2-fusion-mode",),
        {
            "default": "linear",
            "show_default": True,
            "type": click.Choice(list(HYBRID_FUSION_CHOICES), case_sensitive=False),
            "help": "Fusion mode for hybrid_re2 ranker.",
        },
    ),
    (
        ("--hybrid-re2-rrf-k",),
        {
            "default": 60,
            "show_default": True,
            "type": int,
            "help": "RRF k parameter for hybrid fusion.",
        },
    ),
)


SHARED_EMBEDDING_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--embedding-enabled/--no-embedding-enabled",),
        {
            "default": False,
            "show_default": True,
            "help": "Enable embedding-based candidate rerank fusion.",
        },
    ),
    (
        ("--embedding-provider",),
        {
            "default": "hash",
            "show_default": True,
            "type": click.Choice(list(EMBEDDING_PROVIDER_CHOICES), case_sensitive=False),
            "help": "Embedding provider implementation.",
        },
    ),
    (
        ("--embedding-model",),
        {
            "default": "hash-v1",
            "show_default": True,
            "help": "Embedding model identifier for cache compatibility.",
        },
    ),
    (
        ("--embedding-dimension",),
        {
            "default": 256,
            "show_default": True,
            "type": int,
            "help": "Embedding vector dimension.",
        },
    ),
    (
        ("--embedding-index-path",),
        {
            "default": "context-map/embeddings/index.json",
            "show_default": True,
            "type": click.Path(path_type=str),
            "help": "Persistent embedding index path.",
        },
    ),
    (
        ("--embedding-rerank-pool",),
        {
            "default": 24,
            "show_default": True,
            "type": int,
            "help": "How many top lexical candidates enter embedding rerank.",
        },
    ),
    (
        ("--embedding-lexical-weight",),
        {
            "default": 0.7,
            "show_default": True,
            "type": float,
            "help": "Fusion weight for lexical score.",
        },
    ),
    (
        ("--embedding-semantic-weight",),
        {
            "default": 0.3,
            "show_default": True,
            "type": float,
            "help": "Fusion weight for embedding similarity.",
        },
    ),
    (
        ("--embedding-min-similarity",),
        {
            "default": 0.0,
            "show_default": True,
            "type": float,
            "help": "Minimum cosine similarity retained for embedding signal.",
        },
    ),
    (
        ("--embedding-fail-open/--no-embedding-fail-open",),
        {
            "default": True,
            "show_default": True,
            "help": "Keep lexical ranking when embedding runtime fails.",
        },
    ),
)


SHARED_LSP_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--lsp/--no-lsp", "lsp_enabled"),
        {
            "default": False,
            "show_default": True,
            "help": "Enable LSP diagnostics augment stage.",
        },
    ),
    (
        ("--lsp-top-n",),
        {
            "default": 5,
            "show_default": True,
            "type": int,
            "help": "Top candidate files for LSP diagnostics.",
        },
    ),
    (
        ("--lsp-cmd", "lsp_cmds"),
        {
            "multiple": True,
            "help": "LSP command mapping, e.g. python='pyright --outputjson'.",
        },
    ),
    (
        ("--lsp-xref/--no-lsp-xref", "lsp_xref_enabled"),
        {
            "default": False,
            "show_default": True,
            "help": "Enable LSP xref augment flow.",
        },
    ),
    (
        ("--lsp-xref-top-n",),
        {
            "default": 3,
            "show_default": True,
            "type": int,
            "help": "Top candidate files for xref collection.",
        },
    ),
    (
        ("--lsp-time-budget-ms",),
        {
            "default": 1500,
            "show_default": True,
            "type": int,
            "help": "Time budget for xref collection in milliseconds.",
        },
    ),
    (
        ("--lsp-xref-cmd", "lsp_xref_cmds"),
        {
            "multiple": True,
            "help": "LSP xref command mapping, e.g. python='python scripts/xref.py --file {file} --query {query}'.",
        },
    ),
)


SHARED_COCHANGE_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--cochange/--no-cochange", "cochange_enabled"),
        {
            "default": True,
            "show_default": True,
            "help": "Enable Git co-change signal.",
        },
    ),
    (
        ("--cochange-cache-path",),
        {
            "default": "context-map/cochange.json",
            "show_default": True,
            "type": click.Path(path_type=str),
            "help": "Cache path for co-change matrix.",
        },
    ),
    (
        ("--cochange-lookback-commits",),
        {
            "default": 400,
            "show_default": True,
            "type": int,
            "help": "How many commits to scan when building co-change matrix.",
        },
    ),
    (
        ("--cochange-half-life-days",),
        {
            "default": 60.0,
            "show_default": True,
            "type": float,
            "help": "Recency half-life days for co-change decay.",
        },
    ),
    (
        ("--cochange-top-neighbors",),
        {
            "default": 12,
            "show_default": True,
            "type": int,
            "help": "Top neighbors expanded from co-change graph.",
        },
    ),
    (
        ("--cochange-boost-weight",),
        {
            "default": 1.5,
            "show_default": True,
            "type": float,
            "help": "Boost weight applied to co-change neighbors.",
        },
    ),
)


SHARED_POLICY_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--retrieval-policy",),
        {
            "default": "auto",
            "show_default": True,
            "type": click.Choice(list(RETRIEVAL_POLICY_CHOICES), case_sensitive=False),
            "help": "Intent-aware retrieval policy.",
        },
    ),
    (
        ("--policy-version",),
        {
            "default": "v1",
            "show_default": True,
            "help": "Policy version tag written to observability.",
        },
    ),
)


SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--junit-xml", "--failed-test-report", "junit_xml"),
        {
            "default": None,
            "type": click.Path(path_type=str),
            "help": "Optional failed test report path (JUnit XML format).",
        },
    ),
    (
        ("--coverage-json",),
        {
            "default": None,
            "type": click.Path(path_type=str),
            "help": "Optional coverage JSON path for augment test signals.",
        },
    ),
    (
        ("--sbfl-json",),
        {
            "default": None,
            "type": click.Path(path_type=str),
            "help": "Optional SBFL JSON path for augment test signals.",
        },
    ),
    (
        ("--sbfl-metric",),
        {
            "default": "ochiai",
            "show_default": True,
            "type": click.Choice(list(SBFL_METRIC_CHOICES), case_sensitive=False),
            "help": "SBFL scoring metric when SBFL JSON provides execution counts.",
        },
    ),
)


SHARED_SCIP_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--scip/--no-scip", "scip_enabled"),
        {
            "default": False,
            "show_default": True,
            "help": "Enable SCIP/xref ranking fusion.",
        },
    ),
    (
        ("--scip-index-path",),
        {
            "default": "context-map/scip/index.json",
            "show_default": True,
            "type": click.Path(path_type=str),
            "help": "SCIP/xref index path.",
        },
    ),
    (
        ("--scip-provider",),
        {
            "default": "auto",
            "show_default": True,
            "type": click.Choice(list(SCIP_PROVIDER_CHOICES), case_sensitive=False),
            "help": "Index protocol/provider for SCIP ingest.",
        },
    ),
    (
        ("--scip-generate-fallback/--no-scip-generate-fallback",),
        {
            "default": True,
            "show_default": True,
            "help": "Generate scip-lite fallback when ingest source is missing/invalid.",
        },
    ),
)


SHARED_TRACE_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--trace-export/--no-trace-export", "trace_export_enabled"),
        {
            "default": False,
            "show_default": True,
            "help": "Export stage-level trace spans to JSONL.",
        },
    ),
    (
        ("--trace-export-path",),
        {
            "default": "context-map/traces/stage_spans.jsonl",
            "show_default": True,
            "type": click.Path(path_type=str),
            "help": "JSONL output path for stage trace spans.",
        },
    ),
    (
        ("--trace-otlp/--no-trace-otlp", "trace_otlp_enabled"),
        {
            "default": False,
            "show_default": True,
            "help": "Enable OTLP trace export (file/http endpoint).",
        },
    ),
    (
        ("--trace-otlp-endpoint",),
        {
            "default": "",
            "show_default": "(disabled)",
            "help": "OTLP endpoint (http(s) URL or file path / file://path).",
        },
    ),
    (
        ("--trace-otlp-timeout-seconds",),
        {
            "default": 1.5,
            "show_default": True,
            "type": float,
            "help": "Timeout for OTLP export requests.",
        },
    ),
)


__all__ = [
    "CANDIDATE_RANKER_CHOICES",
    "CHUNK_DISCLOSURE_CHOICES",
    "EMBEDDING_PROVIDER_CHOICES",
    "HYBRID_FUSION_CHOICES",
    "ADAPTIVE_ROUTER_MODE_CHOICES",
    "MEMORY_AUTO_TAG_MODE_CHOICES",
    "MEMORY_GATE_MODE_CHOICES",
    "MEMORY_STRATEGY_CHOICES",
    "OptionDescriptor",
    "REMOTE_SLOT_POLICY_CHOICES",
    "RETRIEVAL_POLICY_CHOICES",
    "RETRIEVAL_PRESETS",
    "RETRIEVAL_PRESET_CHOICES",
    "SBFL_METRIC_CHOICES",
    "SCIP_PROVIDER_CHOICES",
    "SHARED_CANDIDATE_OPTION_DESCRIPTORS",
    "SHARED_CHUNK_OPTION_DESCRIPTORS",
    "SHARED_COCHANGE_OPTION_DESCRIPTORS",
    "SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS",
    "SHARED_EMBEDDING_OPTION_DESCRIPTORS",
    "SHARED_LSP_OPTION_DESCRIPTORS",
    "SHARED_MEMORY_OPTION_DESCRIPTORS",
    "SHARED_SKILLS_OPTION_DESCRIPTORS",
    "SHARED_POLICY_OPTION_DESCRIPTORS",
    "SHARED_SCIP_OPTION_DESCRIPTORS",
    "SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS",
    "SHARED_TRACE_OPTION_DESCRIPTORS",
    "_build_option_decorators",
]
