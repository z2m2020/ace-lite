# ACE-Lite Team Playbook

Date: `2026-03-24`

This guide turns ACE-Lite usage into an auditable engineering workflow.
The goal is not "use ACE-Lite more". The goal is "use it predictably enough that retrieval output can be checked, discussed, and reused".

## 1. Standard Workflow

Use this sequence as the default team path:

1. `ace_health`
2. `ace_memory_search`
3. `ace_plan_quick`
4. Read the top candidate files and collect evidence
5. Escalate to `ace_plan` only when the quick shortlist is not enough
6. `ace_memory_store` after the task is resolved

Rules:

- Do not skip memory search for recurring problem areas.
- Do not treat `ace_plan_quick` or `ace_plan` output as a conclusion by itself.
- A candidate file is only promoted after manual evidence review.
- Every final conclusion should point to `file:line`.

## 2. Query Rules

### 2.1 Preferred Query Shape

Write queries around behavior, symptom, scope, and impact.

Recommended template:

```text
[target behavior] in [module boundary] shows [observable symptom]; locate implementation path, error handling, observability, and weak test coverage.
```

Examples:

```text
runtime status in CLI support shows degraded memory health; locate the aggregation path, output rendering, and tests that lock the contract
```

```text
validation retry handling in post-source runtime can loop without enough evidence; locate action routing, stop conditions, and replay-safe summaries
```

### 2.2 Anti-Patterns

Avoid:

- file-name-only queries
- symbol-name-only queries when the behavior is the real question
- overloaded queries that mix unrelated modules
- vague prompts such as `optimize`, `improve`, or `fix issue` without a symptom

Bad:

```text
index_cache.py
```

```text
improve memory
```

Better:

```text
incremental index refresh reuses stale cache after git-only metadata changes; locate fingerprint calculation, cache invalidation, and replay boundary
```

## 3. Evidence Gate

ACE-Lite is allowed to shortlist.
Humans are still responsible for evidence closure.

Before implementation or architectural conclusions:

1. Read the top candidate files
2. Confirm the actual call path or contract
3. Record at least one `file:line` reference per major claim

For non-trivial tasks, cover these evidence classes:

- entry point
- state mutation or config resolution point
- output or user-visible rendering point
- test or benchmark coverage point

If you cannot produce a `file:line` chain, the conclusion is still provisional.

## 4. Large Result Handling

Use ACE-Lite output as an index, not as a document to consume whole.

Preferred pattern:

1. Run `ace_plan_quick`
2. Extract the top candidate files
3. Read only the files that remain plausible
4. Escalate to `ace_plan` only when richer payload is necessary
5. Convert the final result into a short evidence chain

Do not read the entire `ace_plan` payload first.
That increases reading cost and weakens prioritization discipline.

## 5. Fallback Ladder

When the tool starts drifting, follow a fixed downgrade sequence:

1. Rewrite the query to be behavior-first
2. Retry with `ace_plan_quick`
3. Read the core entry file manually
4. Re-run `ace_plan` only if the shortlist is now stable
5. Rebuild the index when retrieval quality is still off

Suggested command:

```bash
ace-lite index --root . --output context-map/index.json
```

Path hygiene rules:

- confirm the current working directory before planning
- do not rely on deleted worktrees or stale temporary roots
- if the target root is unstable, fall back to the main repo root first

## 6. Review Gates

For code review and design review:

- every material claim should include `file:line`
- if ACE-Lite influenced the change, reviewers should verify the evidence chain rather than the raw retrieval output
- query wording should be inspectable when retrieval materially influenced the change
- tasks that touched memory or ranking should confirm whether `ace_memory_store` was updated when appropriate

## 7. Weekly Metrics

Track these per week:

1. first-pass hit rate
2. mean candidate file count
3. drift or retry count
4. time from retrieval to actionable conclusion
5. memory write-back rate after completed tasks

Optional quality buckets:

- query-quality issue
- candidate-noise issue
- path/worktree issue
- missing-evidence issue

## 8. End-of-Task Checklist

Before closing a task that used ACE-Lite:

- `ace_health` was checked
- memory search was used or intentionally skipped with reason
- shortlisted files were manually read
- conclusion includes `file:line`
- fallback path was used if retrieval drifted
- durable memory was stored when the task created reusable knowledge

## 9. Recommended Adoption Order

Roll this out in order:

1. standardize the workflow
2. enforce `file:line` evidence in PRs
3. normalize query templates
4. add a weekly retrieval-quality review
5. build a small internal query template library for repeated scenarios
