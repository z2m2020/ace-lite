---
name: mem0-iteration-loop
description: Iterative Mem0 and OpenMemory retrieval-tuning loop for noisy, stale, or duplicate memory results.
intents: [memory, review]
modules: [memory, retrieval, quality, profile, postprocess, feedback, capture]
error_keywords: [noise, stale, duplicate, 噪声, 过期, 重复]
default_sections: [Scorecard, Iteration Checklist, Artifact Checklist, Weekly Cadence]
topics: [mem0, openmemory, utility, retrieval_hygiene, recall_at_k, precision_at_k, memory_profile, memory_postprocess, memory_feedback, memory_capture, notes_mode, 记忆, 检索质量, 质量]
priority: 2
token_estimate: 240
---

# Scorecard

Track the same indicators every cycle:

- `recall_at_k`
- `precision_at_k`
- `utility_rate`
- `noise_rate`
- `stale_hit_rate`
- `duplicate_hit_rate`

# Iteration Checklist

Before comparing runs, hold these steady unless they are the variable under test:

- scope filters: repo, user, app, namespace
- profile and budget settings
- postprocess thresholds and noise filtering
- notes/capture/feedback writeback policy
- embedding model and collection dimension

# Artifact Checklist

Store the same artifacts for every comparison run:

- benchmark case set or prompt batch
- scope snapshot: repo, user, app, namespace
- embedding model and dimension
- profile and postprocess settings
- ranked result sample or evaluation output

# Weekly Cadence

1. Freeze one benchmark case set and one repo revision.
2. Record the baseline before changing prompts, filters, dimensions, or lifecycle settings.
3. Change one variable only: retrieval scope, embedding choice, ranking, profile, postprocess, or writeback policy.
4. Re-run the same benchmark and compare deltas against the baseline.
5. Keep the change only if utility improves without raising noise, stale hits, or duplicate hits.
6. Store the conclusion as a reusable memory rule if it will matter next week.
