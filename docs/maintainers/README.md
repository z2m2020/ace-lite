# Maintainers Docs

This directory keeps the smaller set of maintainer documents that remain useful
for the public repository.

## Public maintainer docs

- `ONBOARDING.md`
- `SYSTEM_MAP.md`
- `BENCHMARKING.md`
- `RELEASING.md`
- `QUALITY_GOVERNANCE.md`
- `ADAPTIVE_PROMOTION_GOVERNANCE_2026-03-09.md`
- `TASK_AWARE_RETRIEVAL_TAXONOMY_2026-03-06.md`
- `TRACING_EXPORT.md`
- `XREF_INGEST.md`

## Suggested entrypoints

- cross-cutting architecture changes: start with `SYSTEM_MAP.md`, then pair `docs/design/ARCHITECTURE_OVERVIEW.md` and `docs/design/ORCHESTRATOR_DESIGN.md`
- release or RC work: start with `RELEASING.md`, then cross-check `BENCHMARKING.md` and `QUALITY_GOVERNANCE.md`
- maintainability refactors: pair `QUALITY_GOVERNANCE.md` with `docs/design/ARCHITECTURE_OVERVIEW.md` and `docs/design/ORCHESTRATOR_DESIGN.md` so the refactor guard suites and documented seams stay in sync

Short-lived planning notes and disposable local context artifacts are
intentionally excluded from this public repository.
