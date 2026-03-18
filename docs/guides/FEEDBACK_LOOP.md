# Feedback Loop Playbook (ACE-Lite)

This document standardizes how to record selection feedback, export and replay it deterministically, and tune the feedback reranker without bypassing benchmark gates.

## 1) Decide which config path you are exercising

ACE-Lite exposes feedback in two places:

- `plan.memory.feedback`: interactive plan reranking
- `benchmark.memory.feedback`: offline benchmark replay

Example `.ace-lite.yml` for interactive plans:

```yaml
plan:
  memory:
    feedback:
      enabled: true
      path: "~/.ace-lite/preference_capture.db"
      max_entries: 512
      boost_per_select: 0.15
      max_boost: 0.6
      decay_days: 60.0
```

Example `.ace-lite.yml` for benchmark replay:

```yaml
benchmark:
  memory:
    feedback:
      enabled: true
      path: "~/.ace-lite/preference_capture.db"
      max_entries: 512
      boost_per_select: 0.15
      max_boost: 0.6
      decay_days: 60.0
```

Notes:

- Feedback events are stored locally in the durable feedback/preference store at `path`.
- Canonical new installs should point `path` at a SQLite store such as `~/.ace-lite/preference_capture.db`.
- Legacy `profile.json` paths are still accepted for compatibility; ACE-Lite will resolve the durable feedback store next to that file.
- Decay is time-based (half-life days) and applied deterministically.
- Use the same feedback store path only when you intentionally want plan-time usage and benchmark replay to share the exact same feedback corpus.

## 2) Record feedback from CLI or MCP hosts

Record a selected file path for a query:

```bash
ace-lite feedback record internal/app/api/shutdown/allowlist.go --query "shutdown allowlist middleware" --repo demo
```

If the host gives you an absolute path, pass `--root` so ACE-Lite stores a repo-relative path that can match benchmark and plan candidates later:

```bash
ace-lite feedback record /workspace/demo/internal/app/api/shutdown/allowlist.go --query "shutdown allowlist middleware" --repo demo --root /workspace/demo
```

If you also want to track which rank position the user picked (for analysis only):

```bash
ace-lite feedback record internal/app/api/shutdown/allowlist.go --query "shutdown allowlist middleware" --repo demo --position 2
```

For MCP hosts, prefer `ace_feedback_record` with the same `root` the MCP server uses for planning. That keeps host-selected absolute paths stable across Windows, WSL, and local replay.

## 3) Inspect feedback stats before tuning

Show a quick summary and the current boost map:

```bash
ace-lite feedback stats --repo demo
ace-lite feedback stats --repo demo --query "shutdown allowlist middleware"
```

Tune the boost configuration in stats mode before changing runtime config:

```bash
ace-lite feedback stats --repo demo --query "shutdown allowlist middleware" --boost-per-select 0.20 --max-boost 0.80 --decay-days 45
```

Interpretation:

- `matched_event_count`: how many stored events overlap the query terms
- `unique_paths`: how many candidate paths can receive a boost
- `paths[*].boost`: the capped boost that would be applied during rerank

## 4) Export and replay feedback offline

Freeze a feedback corpus into an artifact:

```bash
ace-lite feedback export --repo demo --output artifacts/feedback/demo.jsonl
```

Replay the exact corpus into a clean profile for offline experiments:

```bash
ace-lite feedback replay --input artifacts/feedback/demo.jsonl --repo demo --reset --profile-path artifacts/feedback/replay-preference.db
```

Replay tips:

- Use `--reset` when you want deterministic reproduction instead of appending to an existing feedback store.
- Pass `--root` during replay if the exported events contain absolute file paths from an MCP host.
- Keep exported feedback under `artifacts/` or another disposable path; the durable feedback store remains the runtime source of truth.

## 5) Verify feedback is applied in a plan

Run a plan on the same repo and inspect `plan.index.feedback` in the payload:

```bash
ace-lite plan --query "shutdown allowlist middleware" --repo demo --root . --skills-dir skills --memory-primary none --memory-secondary none
```

Expected behavior:

- The no-feedback baseline stays stable when feedback is disabled.
- When feedback is enabled, matching past selections increase candidate scores with a capped, explainable boost.
- `plan.index.feedback.reason` should move from `disabled` or `no_events` to `ok` only when matching events exist.

## 6) Regression-gated offline loop

A practical feedback replay loop looks like this:

1. Run a baseline benchmark with feedback disabled.
2. Record or replay a small batch of real selection events into a dedicated profile.
3. Run the same benchmark with `benchmark.memory.feedback.enabled: true`.
4. Compare both outputs before adopting any tuning changes.

If you prefer a dedicated experiment harness, use the feature-slice runner:

```bash
python scripts/run_feature_slice_matrix.py --config benchmark/matrix/feature_slices.yaml --output-dir artifacts/benchmark/slices/latest
```

The feedback slice is considered healthy only when it clears both gates in `benchmark/matrix/feature_slices.yaml`:

- `precision_delta_min`
- `noise_delta_min`

If you prefer results-based comparison, use the benchmark artifacts (`results.json` / `summary.json`) and a diff report:

```bash
ace-lite benchmark diff --a artifacts/benchmark/baseline/results.json --b artifacts/benchmark/tuned/results.json --output artifacts/benchmark/diff/latest
```

## 7) LTR tuning knobs

These controls are intentionally simple. Treat them like bounded heuristic weights, not free-form ML training.

| Knob | Default | When to increase | When to decrease | Main risk |
| --- | --- | --- | --- | --- |
| `boost_per_select` | `0.15` | Matching feedback is too weak to move obviously correct files | A few selections reorder results too aggressively | Precision improves locally but noise rises elsewhere |
| `max_boost` | `0.6` | Repeated selections should matter more than single picks | A path keeps dominating even when lexical evidence is weak | Overfitting to a small feedback corpus |
| `decay_days` | `60.0` | Teams work on long-lived domains with stable file ownership | Recent behavior should outweigh stale history | Old incidents keep biasing new queries |
| `max_entries` | `512` | You want a larger replay corpus for stable domains | Profiles are too noisy or dominated by old sessions | Store keeps irrelevant history too long |

Safe operating rules:

- Change one knob at a time and rerun the feedback slice after each change.
- Do not raise `boost_per_select` and `max_boost` together in the same experiment unless the baseline was clearly underpowered.
- Prefer lowering `decay_days` before lowering `max_boost` when the problem is stale history rather than absolute score size.
- Keep default runtime behavior fail-open: if the feedback slice does not show measurable precision gain without unacceptable noise, do not promote the tuned config.
