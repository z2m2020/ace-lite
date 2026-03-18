"""Core shared option descriptor families for CLI commands."""

from __future__ import annotations

import os

import click

from ace_lite.cli_app.params_option_catalog import (
    ADAPTIVE_ROUTER_MODE_CHOICES,
    MEMORY_AUTO_TAG_MODE_CHOICES,
    MEMORY_STRATEGY_CHOICES,
)
from ace_lite.cli_app.params_option_registry import OptionDescriptor

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

SHARED_TARGET_OPTION_DESCRIPTORS: tuple[OptionDescriptor, ...] = (
    (
        ("--repo",),
        {
            "required": True,
            "help": "Repository identifier.",
        },
    ),
    (
        ("--root",),
        {
            "required": True,
            "type": click.Path(path_type=str),
            "help": "Repository root path.",
        },
    ),
    (
        ("--skills-dir",),
        {
            "default": "skills",
            "show_default": True,
            "type": click.Path(path_type=str),
            "help": "Markdown skills directory.",
        },
    ),
    (
        ("--config-pack",),
        {
            "default": None,
            "envvar": "ACE_LITE_CONFIG_PACK",
            "show_default": "env ACE_LITE_CONFIG_PACK",
            "type": click.Path(path_type=str),
            "help": "Optional config pack JSON path to apply tuned overrides.",
        },
    ),
    (
        ("--time-range",),
        {
            "default": None,
            "type": str,
            "help": "Optional time window for temporal filtering (e.g., 24h, 7d, 2w).",
        },
    ),
    (
        ("--start-date",),
        {
            "default": None,
            "type": str,
            "help": "Optional ISO start date/datetime for temporal filtering (UTC unless configured).",
        },
    ),
    (
        ("--end-date",),
        {
            "default": None,
            "type": str,
            "help": "Optional ISO end date/datetime for temporal filtering (UTC unless configured).",
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

__all__ = [
    "SHARED_ADAPTIVE_ROUTER_OPTION_DESCRIPTORS",
    "SHARED_MEMORY_OPTION_DESCRIPTORS",
    "SHARED_PLAN_REPLAY_OPTION_DESCRIPTORS",
    "SHARED_SKILLS_OPTION_DESCRIPTORS",
    "SHARED_TARGET_OPTION_DESCRIPTORS",
]
