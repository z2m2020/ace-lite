# Feedback Guide

Use `ace-lite feedback` to record and inspect selection feedback for reranking and issue workflows.

Recommended reading:
- [Feedback Loop](./FEEDBACK_LOOP.md)
- [Session Feedback Capture](./SESSION_FEEDBACK_CAPTURE.md)

## Common Commands

Record a selected path back into the local feedback store:

```text
ace-lite feedback record path/to/file.py \
  --query "shutdown config refresh" \
  --repo my-repo \
  --root /abs/repo/root \
  --profile-path context-map/profile.json
```

Inspect boosts and per-path explainability for a query:

```text
ace-lite feedback stats \
  --repo my-repo \
  --query "shutdown config refresh" \
  --root /abs/repo/root \
  --profile-path context-map/profile.json
```

Inspect the unified developer feedback view for another repository:

```text
ace-lite feedback dev-feedback-summary \
  --repo my-repo \
  --root /abs/repo/root
```

## Root Scope

- When `profile-path` or issue-store paths are relative, they are resolved under `--root`.
- Use the same `--root` for `feedback record` and `feedback stats`; otherwise reads and writes can land in different stores.
- `dev-feedback-summary` also uses `--root` to locate the target repo's `context-map/issue_reports.db`.
