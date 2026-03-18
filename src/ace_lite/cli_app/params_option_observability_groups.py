"""Observability-oriented shared option descriptor families for CLI commands."""

from __future__ import annotations

import click

from ace_lite.cli_app.params_option_catalog import (
    RETRIEVAL_POLICY_CHOICES,
    SBFL_METRIC_CHOICES,
    SCIP_PROVIDER_CHOICES,
)
from ace_lite.cli_app.params_option_registry import OptionDescriptor

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
    "SHARED_COCHANGE_OPTION_DESCRIPTORS",
    "SHARED_LSP_OPTION_DESCRIPTORS",
    "SHARED_POLICY_OPTION_DESCRIPTORS",
    "SHARED_SCIP_OPTION_DESCRIPTORS",
    "SHARED_TEST_SIGNAL_OPTION_DESCRIPTORS",
    "SHARED_TRACE_OPTION_DESCRIPTORS",
]
