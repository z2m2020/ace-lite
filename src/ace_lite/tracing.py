from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ace_lite.http_utils import safe_urlopen
from ace_lite.pipeline.types import StageMetric

TRACE_SCHEMA_VERSION = "ace-lite-trace-v2"
TRACE_COMPAT_SCHEMA_VERSION = "ace-lite-trace-v1"


def _stable_span_id(*, trace_id: str, name: str, index: int) -> str:
    digest = hashlib.sha256(f"{trace_id}:{name}:{index}".encode()).hexdigest()
    return digest[:16]


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _to_unix_nano(value: datetime) -> int:
    normalized = value.astimezone(timezone.utc)
    return int(normalized.timestamp() * 1_000_000_000)


def _normalize_tags(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _duration_ns(elapsed_ms: float) -> int:
    return max(0, round(float(elapsed_ms) * 1_000_000.0))


def _build_trace_rows(
    *,
    query: str,
    repo: str,
    root: str,
    started_at: datetime,
    total_ms: float,
    stage_metrics: list[StageMetric],
    pipeline_order: list[str],
    plugin_policy_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized_started = started_at.astimezone(timezone.utc)
    normalized_total_ms = max(0.0, float(total_ms))
    end_at = normalized_started + timedelta(milliseconds=normalized_total_ms)

    trace_seed = f"{repo}|{root}|{query}|{_iso_utc(normalized_started)}"
    trace_digest = hashlib.sha256(trace_seed.encode("utf-8")).hexdigest()
    trace_id = trace_digest[:24]
    otel_trace_id = trace_digest[:32]

    resource_attributes: dict[str, Any] = {
        "service.name": "ace-lite-engine",
        "service.namespace": "ace_lite",
        "service.instance.id": hashlib.sha256(
            f"{repo}|{root}".encode()
        ).hexdigest()[:12],
        "deployment.environment": "local",
    }

    rows: list[dict[str, Any]] = []
    root_span_id = _stable_span_id(trace_id=otel_trace_id, name="pipeline", index=0)
    root_start_ns = _to_unix_nano(normalized_started)
    root_end_ns = _to_unix_nano(end_at)
    root_duration_ns = _duration_ns(normalized_total_ms)

    rows.append(
        {
            "version": TRACE_COMPAT_SCHEMA_VERSION,
            "schema_version": TRACE_SCHEMA_VERSION,
            "compat_schema_version": TRACE_COMPAT_SCHEMA_VERSION,
            "trace_id": trace_id,
            "otel_trace_id": otel_trace_id,
            "span_id": root_span_id,
            "parent_span_id": None,
            "kind": "pipeline",
            "name": "ace_lite.pipeline",
            "repo": repo,
            "root": root,
            "query_hash": hashlib.sha256(str(query).encode("utf-8")).hexdigest()[:16],
            "pipeline_order": list(pipeline_order),
            "started_at": _iso_utc(normalized_started),
            "ended_at": _iso_utc(end_at),
            "start_time_unix_nano": root_start_ns,
            "end_time_unix_nano": root_end_ns,
            "elapsed_ms": round(normalized_total_ms, 6),
            "duration_ns": root_duration_ns,
            "plugin_policy_summary": dict(plugin_policy_summary or {}),
            "resource": {"attributes": resource_attributes},
            "otel": {
                "trace_id": otel_trace_id,
                "span_id": root_span_id,
                "parent_span_id": None,
                "span_kind": "INTERNAL",
                "status_code": "OK",
            },
            "openinference": {
                "span.kind": "CHAIN",
                "session.id": f"{repo}:{resource_attributes['service.instance.id']}",
            },
            "attributes": {
                "ace.pipeline.order": list(pipeline_order),
                "ace.pipeline.stage_count": len(stage_metrics),
            },
        }
    )

    offset_ms = 0.0
    for index, metric in enumerate(stage_metrics, start=1):
        duration_ms = max(0.0, float(metric.elapsed_ms))
        span_start = normalized_started + timedelta(milliseconds=offset_ms)
        span_end = span_start + timedelta(milliseconds=duration_ms)
        offset_ms += duration_ms

        stage_name = str(metric.stage)
        tags = _normalize_tags(metric.tags)
        plugins = list(metric.plugins) if isinstance(metric.plugins, list) else []
        span_id = _stable_span_id(
            trace_id=otel_trace_id,
            name=stage_name,
            index=index,
        )
        start_ns = _to_unix_nano(span_start)
        end_ns = _to_unix_nano(span_end)
        duration_ns = _duration_ns(duration_ms)

        attributes: dict[str, Any] = {
            "ace.stage": stage_name,
            "ace.stage.index": index - 1,
            "ace.stage.plugin_count": len(plugins),
        }
        for key, value in tags.items():
            normalized_key = str(key).strip()
            if not normalized_key:
                continue
            attributes[f"ace.tag.{normalized_key}"] = value

        rows.append(
            {
                "version": TRACE_COMPAT_SCHEMA_VERSION,
                "schema_version": TRACE_SCHEMA_VERSION,
                "compat_schema_version": TRACE_COMPAT_SCHEMA_VERSION,
                "trace_id": trace_id,
                "otel_trace_id": otel_trace_id,
                "span_id": span_id,
                "parent_span_id": root_span_id,
                "kind": "stage",
                "name": f"ace_lite.stage.{stage_name}",
                "stage": stage_name,
                "stage_index": index - 1,
                "started_at": _iso_utc(span_start),
                "ended_at": _iso_utc(span_end),
                "start_time_unix_nano": start_ns,
                "end_time_unix_nano": end_ns,
                "elapsed_ms": round(duration_ms, 6),
                "duration_ns": duration_ns,
                "plugin_count": len(plugins),
                "plugins": plugins,
                "tags": tags,
                "resource": {"attributes": resource_attributes},
                "otel": {
                    "trace_id": otel_trace_id,
                    "span_id": span_id,
                    "parent_span_id": root_span_id,
                    "span_kind": "INTERNAL",
                    "status_code": "OK",
                },
                "openinference": {
                    "span.kind": "TOOL",
                    "tool.name": f"pipeline.{stage_name}",
                },
                "attributes": attributes,
            }
        )

    return {
        "trace_id": trace_id,
        "otel_trace_id": otel_trace_id,
        "rows": rows,
        "resource_attributes": resource_attributes,
    }


def export_stage_trace_jsonl(
    *,
    output_path: str | Path,
    query: str,
    repo: str,
    root: str,
    started_at: datetime,
    total_ms: float,
    stage_metrics: list[StageMetric],
    pipeline_order: list[str],
    plugin_policy_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    built = _build_trace_rows(
        query=query,
        repo=repo,
        root=root,
        started_at=started_at,
        total_ms=total_ms,
        stage_metrics=stage_metrics,
        pipeline_order=pipeline_order,
        plugin_policy_summary=plugin_policy_summary,
    )

    rows = built["rows"]
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        for item in rows:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    return {
        "enabled": True,
        "exported": True,
        "path": str(path),
        "trace_id": built["trace_id"],
        "otel_trace_id": built["otel_trace_id"],
        "span_count": len(rows),
        "schema_version": TRACE_SCHEMA_VERSION,
        "format": "jsonl",
        "otel_compatible": True,
        "openinference_compatible": True,
    }


def _to_otlp_any_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"intValue": int(value)}
    if isinstance(value, float):
        return {"doubleValue": float(value)}
    if isinstance(value, list):
        return {
            "arrayValue": {
                "values": [_to_otlp_any_value(item) for item in value]
            }
        }
    return {"stringValue": str(value)}


def _otlp_attributes_from_mapping(values: dict[str, Any]) -> list[dict[str, Any]]:
    attributes: list[dict[str, Any]] = []
    for key, value in values.items():
        name = str(key).strip()
        if not name:
            continue
        attributes.append({"key": name, "value": _to_otlp_any_value(value)})
    return attributes


def _row_to_otlp_span(row: dict[str, Any]) -> dict[str, Any]:
    attributes_raw = row.get("attributes")
    attributes = (
        attributes_raw if isinstance(attributes_raw, dict) else {}
    )
    return {
        "traceId": str(row.get("otel_trace_id") or ""),
        "spanId": str(row.get("span_id") or ""),
        "parentSpanId": str(row.get("parent_span_id") or ""),
        "name": str(row.get("name") or ""),
        "kind": 1,
        "startTimeUnixNano": int(row.get("start_time_unix_nano", 0) or 0),
        "endTimeUnixNano": int(row.get("end_time_unix_nano", 0) or 0),
        "attributes": _otlp_attributes_from_mapping(attributes),
        "status": {"code": 1},
    }


def _build_otlp_payload(*, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"resourceSpans": []}

    first = rows[0]
    resource_raw = first.get("resource")
    resource = resource_raw if isinstance(resource_raw, dict) else {}
    resource_attrs_raw = resource.get("attributes")
    resource_attrs = (
        resource_attrs_raw if isinstance(resource_attrs_raw, dict) else {}
    )

    spans = [_row_to_otlp_span(row) for row in rows if isinstance(row, dict)]
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": _otlp_attributes_from_mapping(resource_attrs)
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "ace_lite.tracing", "version": "v1"},
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def export_stage_trace_otlp(
    *,
    endpoint: str,
    query: str,
    repo: str,
    root: str,
    started_at: datetime,
    total_ms: float,
    stage_metrics: list[StageMetric],
    pipeline_order: list[str],
    plugin_policy_summary: dict[str, Any] | None = None,
    timeout_seconds: float = 1.5,
) -> dict[str, Any]:
    built = _build_trace_rows(
        query=query,
        repo=repo,
        root=root,
        started_at=started_at,
        total_ms=total_ms,
        stage_metrics=stage_metrics,
        pipeline_order=pipeline_order,
        plugin_policy_summary=plugin_policy_summary,
    )
    rows = built["rows"]
    payload = _build_otlp_payload(rows=rows)

    destination = str(endpoint or "").strip()
    if not destination:
        return {
            "enabled": True,
            "exported": False,
            "trace_id": built["trace_id"],
            "otel_trace_id": built["otel_trace_id"],
            "span_count": len(rows),
            "error": "empty_endpoint",
        }

    if destination.startswith("file://"):
        output = Path(destination.replace("file://", "", 1))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "enabled": True,
            "exported": True,
            "transport": "file",
            "endpoint": destination,
            "path": str(output),
            "trace_id": built["trace_id"],
            "otel_trace_id": built["otel_trace_id"],
            "span_count": len(rows),
        }

    if destination.startswith("http://") or destination.startswith("https://"):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            destination,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with safe_urlopen(
                request,
                timeout=max(0.1, float(timeout_seconds)),
            ) as response:
                status = int(getattr(response, "status", 200) or 200)
            return {
                "enabled": True,
                "exported": 200 <= status < 300,
                "transport": "http",
                "endpoint": destination,
                "status_code": status,
                "trace_id": built["trace_id"],
                "otel_trace_id": built["otel_trace_id"],
                "span_count": len(rows),
            }
        except urllib.error.URLError as exc:
            return {
                "enabled": True,
                "exported": False,
                "transport": "http",
                "endpoint": destination,
                "trace_id": built["trace_id"],
                "otel_trace_id": built["otel_trace_id"],
                "span_count": len(rows),
                "error": str(exc),
            }

    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "enabled": True,
        "exported": True,
        "transport": "file",
        "endpoint": destination,
        "path": str(output),
        "trace_id": built["trace_id"],
        "otel_trace_id": built["otel_trace_id"],
        "span_count": len(rows),
    }


__all__ = ["export_stage_trace_jsonl", "export_stage_trace_otlp"]
