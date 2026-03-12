from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "3.2"
EXPECTED_PIPELINE_ORDER = [
    "memory",
    "index",
    "repomap",
    "augment",
    "skills",
    "source_plan",
]
REQUIRED_TOP_LEVEL_KEYS = (
    "schema_version",
    "query",
    "repo",
    "root",
    "pipeline_order",
    "memory",
    "index",
    "repomap",
    "augment",
    "skills",
    "source_plan",
    "observability",
    "conventions",
)


REQUIRED_WRITEBACK_METADATA_KEYS = (
    "repo",
    "branch",
    "path",
    "topic",
    "module",
    "updated_at",
    "app",
)

PLUGIN_POLICY_COUNTER_KEYS = (
    "applied",
    "conflicts",
    "blocked",
    "warn",
    "remote_applied",
)


CHUNK_REF_REQUIRED_KEYS = (
    "path",
    "qualified_name",
    "kind",
    "lineno",
    "end_lineno",
)


def _validate_chunk_skeleton(skeleton: Any, *, prefix: str) -> None:
    if not isinstance(skeleton, dict):
        raise ValueError(f"{prefix} must be a dictionary")

    for key in ("schema_version", "mode", "symbol", "span", "anchors"):
        if key not in skeleton:
            raise ValueError(f"{prefix}.{key} is required")

    if not isinstance(skeleton.get("schema_version"), str):
        raise ValueError(f"{prefix}.schema_version must be a string")
    if not isinstance(skeleton.get("mode"), str):
        raise ValueError(f"{prefix}.mode must be a string")
    if not isinstance(skeleton.get("language"), str):
        raise ValueError(f"{prefix}.language must be a string")
    if not isinstance(skeleton.get("module"), str):
        raise ValueError(f"{prefix}.module must be a string")

    symbol = skeleton.get("symbol")
    if not isinstance(symbol, dict):
        raise ValueError(f"{prefix}.symbol must be a dictionary")
    for key in ("name", "qualified_name", "kind"):
        if not isinstance(symbol.get(key), str):
            raise ValueError(f"{prefix}.symbol.{key} must be a string")

    span = skeleton.get("span")
    if not isinstance(span, dict):
        raise ValueError(f"{prefix}.span must be a dictionary")
    for key in ("start_line", "end_line", "line_count"):
        if not isinstance(span.get(key), (int, float)):
            raise ValueError(f"{prefix}.span.{key} must be numeric")

    anchors = skeleton.get("anchors")
    if not isinstance(anchors, dict):
        raise ValueError(f"{prefix}.anchors must be a dictionary")
    if not isinstance(anchors.get("path"), str):
        raise ValueError(f"{prefix}.anchors.path must be a string")
    if not isinstance(anchors.get("signature"), str):
        raise ValueError(f"{prefix}.anchors.signature must be a string")
    if not isinstance(anchors.get("robust_signature_available"), bool):
        raise ValueError(
            f"{prefix}.anchors.robust_signature_available must be a boolean"
        )

    metadata = skeleton.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError(f"{prefix}.metadata must be a dictionary")

    robust_summary = skeleton.get("robust_signature_summary")
    if robust_summary is not None and not isinstance(robust_summary, dict):
        raise ValueError(f"{prefix}.robust_signature_summary must be a dictionary")


def _validate_plugin_policy_summary(summary: dict[str, Any]) -> None:
    if not isinstance(summary, dict):
        raise ValueError("observability.plugin_policy_summary must be a dictionary")

    mode = summary.get("mode")
    if not isinstance(mode, str):
        raise ValueError("observability.plugin_policy_summary.mode must be a string")

    allowlist = summary.get("allowlist")
    if not isinstance(allowlist, list) or not all(
        isinstance(item, str) for item in allowlist
    ):
        raise ValueError(
            "observability.plugin_policy_summary.allowlist must be a string list"
        )

    totals = summary.get("totals")
    if not isinstance(totals, dict):
        raise ValueError(
            "observability.plugin_policy_summary.totals must be a dictionary"
        )
    for key in PLUGIN_POLICY_COUNTER_KEYS:
        value = totals.get(key)
        if not isinstance(value, (int, float)):
            raise ValueError(
                f"observability.plugin_policy_summary.totals.{key} must be numeric"
            )

    by_stage = summary.get("by_stage")
    if not isinstance(by_stage, list):
        raise ValueError("observability.plugin_policy_summary.by_stage must be a list")
    for item in by_stage:
        if not isinstance(item, dict):
            raise ValueError(
                "observability.plugin_policy_summary.by_stage entries must be dictionaries"
            )
        stage = item.get("stage")
        if not isinstance(stage, str):
            raise ValueError(
                "observability.plugin_policy_summary.by_stage[].stage must be a string"
            )
        for key in PLUGIN_POLICY_COUNTER_KEYS:
            value = item.get(key)
            if not isinstance(value, (int, float)):
                raise ValueError(
                    "observability.plugin_policy_summary.by_stage[]"
                    f".{key} must be numeric"
                )


def _validate_chunk_ref(chunk: dict[str, Any], *, prefix: str) -> None:
    if not isinstance(chunk, dict):
        raise ValueError(f"{prefix} must be a dictionary")

    for key in CHUNK_REF_REQUIRED_KEYS:
        if key not in chunk:
            raise ValueError(f"{prefix}.{key} is required")

    if not isinstance(chunk.get("path"), str):
        raise ValueError(f"{prefix}.path must be a string")
    if not isinstance(chunk.get("qualified_name"), str):
        raise ValueError(f"{prefix}.qualified_name must be a string")
    if not isinstance(chunk.get("kind"), str):
        raise ValueError(f"{prefix}.kind must be a string")
    if not isinstance(chunk.get("lineno"), (int, float)):
        raise ValueError(f"{prefix}.lineno must be numeric")
    if not isinstance(chunk.get("end_lineno"), (int, float)):
        raise ValueError(f"{prefix}.end_lineno must be numeric")
    if "disclosure" in chunk and not isinstance(chunk.get("disclosure"), str):
        raise ValueError(f"{prefix}.disclosure must be a string")
    if "disclosure_requested" in chunk and not isinstance(
        chunk.get("disclosure_requested"), str
    ):
        raise ValueError(f"{prefix}.disclosure_requested must be a string")
    if "disclosure_fallback_reason" in chunk and not isinstance(
        chunk.get("disclosure_fallback_reason"), str
    ):
        raise ValueError(f"{prefix}.disclosure_fallback_reason must be a string")
    if "skeleton_available" in chunk and not isinstance(
        chunk.get("skeleton_available"), bool
    ):
        raise ValueError(f"{prefix}.skeleton_available must be a boolean")
    if "skeleton" in chunk:
        _validate_chunk_skeleton(chunk.get("skeleton"), prefix=f"{prefix}.skeleton")


def _validate_chunk_list(chunks: Any, *, prefix: str) -> None:
    if not isinstance(chunks, list):
        raise ValueError(f"{prefix} must be a list")
    for index, chunk in enumerate(chunks):
        _validate_chunk_ref(chunk, prefix=f"{prefix}[{index}]")


def validate_context_plan(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("context plan must be a dictionary")

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in payload:
            raise ValueError(f"missing required top-level field: {key}")

    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unexpected schema_version: {payload.get('schema_version')}")

    pipeline_order = payload.get("pipeline_order")
    if not isinstance(pipeline_order, list) or not pipeline_order:
        raise ValueError("pipeline_order must be a non-empty list")
    if [str(item) for item in pipeline_order] != EXPECTED_PIPELINE_ORDER:
        raise ValueError(f"unexpected pipeline_order: {pipeline_order}")

    observability = payload.get("observability")
    if not isinstance(observability, dict):
        raise ValueError("observability must be a dictionary")

    stage_metrics = observability.get("stage_metrics")
    if not isinstance(stage_metrics, list):
        raise ValueError("observability.stage_metrics is required")

    plugin_policy_summary = observability.get("plugin_policy_summary")
    if plugin_policy_summary is not None:
        _validate_plugin_policy_summary(plugin_policy_summary)

    index_payload = payload.get("index")
    if isinstance(index_payload, dict) and "candidate_chunks" in index_payload:
        _validate_chunk_list(
            index_payload.get("candidate_chunks"),
            prefix="index.candidate_chunks",
        )

    source_plan = payload.get("source_plan")
    if isinstance(source_plan, dict):
        if "candidate_chunks" in source_plan:
            _validate_chunk_list(
                source_plan.get("candidate_chunks"),
                prefix="source_plan.candidate_chunks",
            )

        chunk_steps = source_plan.get("chunk_steps")
        if chunk_steps is not None:
            if not isinstance(chunk_steps, list):
                raise ValueError("source_plan.chunk_steps must be a list")
            for index, step in enumerate(chunk_steps):
                if not isinstance(step, dict):
                    raise ValueError(
                        "source_plan.chunk_steps entries must be dictionaries"
                    )
                chunk_ref = step.get("chunk_ref")
                if not isinstance(chunk_ref, dict):
                    raise ValueError(
                        f"source_plan.chunk_steps[{index}].chunk_ref must be a dict"
                    )
                _validate_chunk_ref(
                    chunk_ref,
                    prefix=f"source_plan.chunk_steps[{index}].chunk_ref",
                )
                action = step.get("action")
                if not isinstance(action, str):
                    raise ValueError(
                        "source_plan.chunk_steps[].action must be a string"
                    )

        validation_tests = source_plan.get("validation_tests")
        if validation_tests is not None and (
            not isinstance(validation_tests, list)
            or not all(isinstance(item, str) for item in validation_tests)
        ):
            raise ValueError("source_plan.validation_tests must be a string list")

    if isinstance(source_plan, dict):
        template = source_plan.get("writeback_template")
        if isinstance(template, dict):
            metadata = template.get("metadata")
            if isinstance(metadata, dict):
                missing = [
                    key
                    for key in REQUIRED_WRITEBACK_METADATA_KEYS
                    if key not in metadata
                ]
                if missing:
                    raise ValueError(
                        f"source_plan.writeback_template.metadata missing keys: {', '.join(missing)}"
                    )


__all__ = ["EXPECTED_PIPELINE_ORDER", "SCHEMA_VERSION", "validate_context_plan"]
