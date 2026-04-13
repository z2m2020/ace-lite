"""Retrieval-oriented shared option descriptor families for CLI commands."""

from __future__ import annotations

import click

from ace_lite.cli_app.params_option_catalog import (
    CANDIDATE_RANKER_CHOICES,
    CHUNK_DISCLOSURE_CHOICES,
    CHUNK_GUARD_MODE_CHOICES,
    EMBEDDING_PROVIDER_CHOICES,
    HYBRID_FUSION_CHOICES,
    REMOTE_SLOT_POLICY_CHOICES,
    RETRIEVAL_PRESET_CHOICES,
)
from ace_lite.cli_app.params_option_registry import OptionDescriptor
from ace_lite.repomap.ranking import RANKING_PROFILES


def _build_retrieval_preset_help() -> str:
    """Build detailed help text for retrieval presets."""
    presets = {
        "none": "No preset (use explicit flags)",
        "balanced-v1": "Balanced precision/recall for general use",
        "precision-v1": "Higher precision, fewer candidates",
        "recall-v1": "Higher recall, more candidates",
    }
    lines = ["Named retrieval preset overriding candidate/repomap tuning (explicit flags win)."]
    lines.append("Presets:")
    for name, desc in presets.items():
        lines.append(f"  {name}: {desc}")
    return "\n".join(lines)


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
            "help": _build_retrieval_preset_help(),
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

SHARED_INDEX_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--languages",),
        {
            "default": "python,typescript,javascript,go,markdown",
            "show_default": True,
            "help": "Comma-separated index language profile.",
        },
    ),
    (
        ("--index-cache-path",),
        {
            "default": "context-map/index.json",
            "show_default": True,
            "type": click.Path(path_type=str),
            "help": "Distilled index cache path.",
        },
    ),
    (
        ("--index-incremental/--no-index-incremental",),
        {
            "default": True,
            "show_default": True,
            "help": "Enable incremental index refresh from git changed files.",
        },
    ),
    (
        ("--conventions-file", "conventions_files"),
        {
            "multiple": True,
            "help": "Convention file paths relative to --root.",
        },
    ),
    (
        ("--plugins/--no-plugins", "plugins_enabled"),
        {
            "default": True,
            "show_default": True,
            "help": "Enable plugin loading from plugins/.",
        },
    ),
    (
        ("--remote-slot-policy-mode",),
        {
            "default": "strict",
            "show_default": True,
            "type": click.Choice(list(REMOTE_SLOT_POLICY_CHOICES), case_sensitive=False),
            "help": "Policy mode for mcp_remote slot filtering: strict blocks, warn logs only, off disables filtering.",
        },
    ),
    (
        ("--remote-slot-allowlist",),
        {
            "default": "observability.mcp_plugins",
            "show_default": True,
            "help": "Comma-separated slot allowlist for mcp_remote contributions.",
        },
    ),
)

SHARED_REPOMAP_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--repomap/--no-repomap", "repomap_enabled"),
        {
            "default": True,
            "show_default": True,
            "help": "Enable repomap stage for one-hop dependency expansion.",
        },
    ),
    (
        ("--repomap-top-k",),
        {
            "default": 8,
            "show_default": True,
            "type": int,
            "help": "Max seed files entering repomap stage.",
        },
    ),
    (
        ("--repomap-neighbor-limit",),
        {
            "default": 20,
            "show_default": True,
            "type": int,
            "help": "Max one-hop neighbors collected by repomap stage.",
        },
    ),
    (
        ("--repomap-budget-tokens",),
        {
            "default": 800,
            "show_default": True,
            "type": int,
            "help": "Token budget for repomap skeleton markdown.",
        },
    ),
    (
        ("--repomap-ranking-profile",),
        {
            "default": "graph",
            "show_default": True,
            "type": click.Choice(list(RANKING_PROFILES), case_sensitive=False),
            "help": "Ranking profile used by repomap stage.",
        },
    ),
    (
        ("--repomap-signal-weights",),
        {
            "default": None,
            "type": str,
            "help": "Optional JSON object for repomap signal weights.",
        },
    ),
    (
        ("--verbose",),
        {
            "is_flag": True,
            "default": False,
            "help": "Enable debug logging.",
        },
    ),
)

__all__ = [
    "SHARED_CANDIDATE_OPTION_DESCRIPTORS",
    "SHARED_CHUNK_OPTION_DESCRIPTORS",
    "SHARED_EMBEDDING_OPTION_DESCRIPTORS",
    "SHARED_INDEX_OPTION_DESCRIPTORS",
    "SHARED_REPOMAP_OPTION_DESCRIPTORS",
]
