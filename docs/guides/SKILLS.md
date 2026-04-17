# Skills Guide

Use the `skills/` directory as a manifest-driven routing surface, not as a loose note dump. ACE-Lite discovers skill metadata from Markdown frontmatter, ranks skills from query intent and metadata, and only hydrates the selected sections later.

## Inspect The Catalog

If the package entrypoint is available:

```bash
ace-lite skills catalog --root . --skills-dir skills
```

If you are working directly from a source checkout and `ace-lite` is not on `PATH`, use the workspace-safe fallback:

```bash
PYTHONPATH=src python3 -m ace_lite.cli skills catalog --root . --skills-dir skills
```

Use the catalog when you need to confirm which skills are present, their intents, default sections, and token estimates. Do not treat catalog output as a routing oracle; it is a read-only discovery surface.

## Which Skill First

Start with the narrowest skill that matches the task shape. If more than one fits, prefer the skill with the clearest acceptance contract instead of the broadest wording.

| Task shape | Start here | Why |
|---|---|---|
| ACE-Lite internals, retrieval/index/runtime behavior, MCP drift, config surfaces | `ace-dev` | Umbrella skill for ACE-Lite operations, planning loops, doctor flows, and retrieval-sensitive changes. |
| Before editing, need scope, constraints, config surfaces, or artifact expectations | `cross-agent-intake-and-scope` | Pre-change scoping contract that keeps tasks bounded before code edits start. |
| Reproducible bug, failing test, timeout, regression, or install-drift incident | `cross-agent-bugfix-and-regression` | Diagnostics-first bugfix loop with explicit regression and rollback evidence. |
| Refactor that must preserve behavior and contract payloads | `cross-agent-refactor-safeguards` | Protects pipeline, validation, agent-loop, skills-routing, and prompt-boundary contracts during structural cleanup. |
| Release candidate, freeze week, compatibility review, or go/no-go package | `cross-agent-release-readiness` | Release evidence checklist with explicit gate and artifact requirements. |
| Benchmarking or tuning retrieval/routing/validation/agent-loop behavior | `cross-agent-benchmark-tuning-loop` | Baseline-vs-candidate loop with keep-or-rollback rules and artifact discipline. |
| Handoff, resume package, or multi-agent continuity | `cross-agent-handoff-and-context-sync` | Keeps replay, validation, artifact, and routing context reproducible across sessions. |
| Validate ACE-Lite against a real repository and turn misses into feedback/issues/fixes | `cross-agent-repo-validation-and-feedback-loop` | Real-repo evidence loop for route misfires, polluted retrieval, and developer feedback closure. |
| Compare another repository and adapt one small idea safely | `cross-project-borrowing-and-adaptation` | Comparative-analysis workflow for borrowing good patterns without cargo-culting architecture. |
| Mem0/OpenMemory transport issues, `405`, bridge setup, embedding dimension mismatch | `mem0-codex-playbook` | Operations playbook for memory wiring and scope-safe retrieval troubleshooting. |
| Memory quality tuning for noisy, stale, or duplicate results | `mem0-iteration-loop` | Scorecard-style iteration loop for memory retrieval quality over repeated runs. |

## Fast Routing Heuristics

- Use `ace-dev` when the task is specifically about ACE-Lite behavior and you still need to locate the right internal surface.
- Use `cross-agent-*` skills when the task shape is procedural: intake, bugfix, refactor, benchmark, release, handoff, or real-repo validation.
- Use `mem0-*` skills only for memory-specific wiring or retrieval-quality work; do not route generic planning tasks there.
- Use `cross-project-borrowing-and-adaptation` only when there is a real source project or reference implementation to inspect.
- If a generic implementation request has no benchmark, bug, release, handoff, borrowing, or memory signal, it is normal for no specialized skill to be selected.

## Typical Combinations

- `ace-dev` + `cross-agent-bugfix-and-regression`: ACE-Lite runtime bug with explicit diagnostics.
- `ace-dev` + `cross-agent-refactor-safeguards`: ACE-Lite internal refactor that must preserve contract payloads.
- `cross-agent-intake-and-scope` + `ace-dev`: define boundaries first, then inspect ACE-Lite config and retrieval surfaces.
- `cross-agent-repo-validation-and-feedback-loop` + `ace-dev`: validate behavior on a real repository and then patch the smallest ACE-Lite source area.
- `cross-agent-handoff-and-context-sync` + `cross-agent-refactor-safeguards`: hand off a structural change without losing invariants or replay state.

## Practical Workflow

1. Render the skill catalog and confirm the current inventory.
2. Pick the narrowest skill that matches the task shape.
3. Read only that skill and its default sections first.
4. Add a second skill only when the first one clearly lacks the acceptance contract you need.
5. After ACE-Lite code changes, rerun the relevant tests and refresh `context-map/index.json` before trusting later retrieval.

## Related Guides

- [Getting Started](./GETTING_STARTED.md)
- [Plan Guide](./PLAN_GUIDE.md)
- [Diagnostics Guide](./DIAGNOSTICS.md)
- [Memory Guide](./MEMORY.md)
- [Architecture Overview](../design/ARCHITECTURE_OVERVIEW.md)
