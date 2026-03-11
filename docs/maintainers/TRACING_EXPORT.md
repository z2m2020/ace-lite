# Trace Export Guide

ACE-Lite supports deterministic stage trace export in two channels:

1. **JSONL stage spans** (default trace format)
2. **OTLP export** (file/http endpoint)

## CLI

Plan command supports shared trace flags (same for `benchmark run`):

- `--trace-export/--no-trace-export`
- `--trace-export-path context-map/traces/stage_spans.jsonl`
- `--trace-otlp/--no-trace-otlp`
- `--trace-otlp-endpoint file://context-map/traces/stage_spans.otlp.json`
- `--trace-otlp-timeout-seconds 1.5`

Examples:

```bash
ace-lite plan \
  --query "find auth entrypoint" \
  --repo demo \
  --root . \
  --memory-primary none --memory-secondary none \
  --trace-export \
  --trace-export-path context-map/traces/stage_spans.jsonl
```

```bash
ace-lite plan \
  --query "fix flaky test" \
  --repo demo \
  --root . \
  --memory-primary none --memory-secondary none \
  --trace-export \
  --trace-otlp \
  --trace-otlp-endpoint file://context-map/traces/stage_spans.otlp.json
```

## Config keys

Layered config supports both `plan.*` and `benchmark.*` namespaces:

```yaml
plan:
  trace:
    export_enabled: true
    export_path: context-map/traces/stage_spans.jsonl
    otlp_enabled: true
    otlp_endpoint: file://context-map/traces/stage_spans.otlp.json
    otlp_timeout_seconds: 1.5
```

## Output compatibility

JSONL rows keep backward-compatible fields and now include:

- `schema_version: ace-lite-trace-v2`
- OTel-compatible IDs and nanosecond timestamps
- OpenInference-style span metadata

When OTLP export is enabled, `observability.trace_export.otlp` records export status, endpoint, and span count.
