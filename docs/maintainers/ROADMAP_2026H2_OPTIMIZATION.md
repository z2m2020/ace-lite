# H2 2026 Optimization Roadmap

This document captures the optimization opportunities identified during code review and ranks them by implementation priority.

## Guiding Principle

> Continue with additive, outer-layer improvements. Do not rewrite the internal core protocol or data model solely for compatibility or performance.

## Priority Matrix

| # | Optimization Area | Priority | Status | Rationale |
|---|---|---|---|---|
| 1 | Fix broken document references and complete the roadmap | **P0** | Done | Confirmed issue with immediate maintenance value |
| 2 | Stay on the "outer-layer additive optimization" path | **P1** | Ongoing | Architectural direction remains sound |
| 3 | Tighten skill frontmatter linting and CI enforcement | **P1** | Planned | `lint_skill_manifest()` already provides a solid implementation hook |
| 4 | Extract `classify_tier()` into a module-level function | **P1** | Planned | Removes duplicated logic in `indexer.py` |
| 5 | Replace raw `StageContext.state` keys with constants | **P1** | Planned | Improves type safety and reduces key drift |
| 6 | Add persistent caching for skill manifests | **P2** | Deferred | Only 9 skills exist today, so this is not a current bottleneck |
| 7 | Refactor MCP provenance handling in `runtime_settings.py` into an iteration-based pattern | **P2** | Deferred | Primarily a DRY improvement |
| 8 | Expand protocol shims only when concrete integrations require it | **P2** | Deferred | Should be driven by real integration demand |

## Explicit Non-Goals

| Area | Reason |
|---|---|
| More sophisticated skill-routing algorithms | Diminishing returns relative to current complexity |
| A general-purpose MemoryBench platform | Too far from the project's core focus |
| Rewriting the internal memory/profile/core stack | Not worth the cost merely for compatibility |
| Large-scale orchestrator decomposition | High risk with no urgent payoff today |

## Completed Improvements

- Skill loading now follows a "route first, hydrate later" lazy-loading pattern.
- The Supermemory graph view is already implemented in `graph_view.py`.
- The thin protocol compatibility layer has been validated, including `containerTag` fallback behavior.
- Incremental indexing fingerprint support is already working.
