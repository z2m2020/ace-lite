---
name: cross-project-borrowing-and-adaptation
description: Structured comparative analysis workflow for studying an external or reference repository, extracting transferable ideas, rejecting non-fit patterns, and adapting the best insight into a minimal validated improvement for the current project. Use when comparing architecture, tests, reports, or code taste across repositories to turn inspiration into concrete repository changes.
intents: [research, review, refactor, implement]
modules: [architecture, docs, report, benchmark]
error_keywords: []
default_sections: [Workflow, Evidence Checklist, Borrowing Matrix, Borrowing Ledger, Output Contract]
topics: [compare, comparison, analyze, analysis, borrow, borrowing, inspiration, inspired, reference implementation, external repo, architecture review, workflow review, code taste, report contract, graphify, 对标, 借鉴, 灵感, 启发, 分析, 比较, 拆解, 复盘, 参考实现, 代码品味, 架构设计, 流程设计]
priority: 2
token_estimate: 540
---

# Workflow

1. Name the source project, target project, and decision surface before reading code. Good surfaces are: stage boundaries, payload contracts, test shape, CLI/MCP ergonomics, report structure, or skill routing.
2. Read only the highest-signal source artifacts first: architecture or README overview, entrypoint modules, validators or contract guards, report/export code, and one end-to-end test.
3. In the target repo, recover current structure before proposing changes: architecture docs, the closest runtime module, the closest tests, and any public contract or schema notes.
4. Fill the evidence checklist before proposing any adaptation. If the evidence is still weak, stay in analysis mode.
5. Build a borrowing matrix before editing code. Force each candidate idea through fit, cost, and rollback checks.
6. Borrow the smallest high-value idea first. Prefer helper extraction, contract hardening, naming alignment, report/readability improvements, or narrow regression guards over broad rewrites.
7. Preserve what should remain project-specific. Do not copy source-repo abstractions, tooling, or automation just because they exist.
8. Land one minimal improvement, validate it, then update the borrowing ledger with accepted, rejected, and deferred ideas.

# Evidence Checklist

Source evidence checklist:

- Overview doc showing the pipeline or stage order
- One module that validates or normalizes boundary data
- One human-facing report or summary module
- One end-to-end or golden test
- One example of a pattern that should explicitly not be copied

Target evidence checklist:

- Current architecture or design doc
- Runtime code closest to the borrowed idea
- Existing contract or schema assertions
- Focused tests that can guard the adaptation
- One explicit rollback path in the current repo

Readiness rule:

- Do not promote a borrowing candidate into code until both source evidence and target evidence are concrete enough to cite exact files or tests.

# Borrowing Matrix

For each candidate idea, fill these fields before implementation:

- Source pattern: one sentence naming the pattern or habit in the reference repo
- Source evidence: file paths or tests that prove the pattern is real
- Why it works there: the local constraint or product goal it solves
- Fit in our repo: exact target module, contract, or workflow it would improve
- Adaptation shape: the smallest compatible change in our repository
- Non-goals: what not to copy
- Validation: the exact tests or commands that prove the adaptation is safe
- Rollback: the one-step revert path

Quick filters:

- Borrow if it clarifies boundaries, removes repetition, improves auditability, or creates a stronger regression guard.
- Reject if it imports a foreign architecture, adds heavy dependencies, duplicates an existing subsystem, or hides behavior behind fragile prompt logic.
- Defer if the idea is valid but requires a wider contract migration than the current task can safely absorb.

# Borrowing Ledger

After each iteration, record the shortlist in this flat ledger:

- Accepted borrowing: idea adopted now, with target files and validation evidence
- Rejected borrowing: idea explicitly not adopted, with the mismatch reason
- Deferred borrowing: idea kept for later, with the blocking contract or migration cost
- Next candidate: the most promising remaining idea if another iteration is justified

Ledger rule:

- The ledger must distinguish "not a fit" from "good idea but too wide for this patch". This is what makes the skill reusable instead of turning it into one-off project notes.

# Prompt Template

- Source project: <repo/path/revision>
- Target project: <repo/path/revision>
- Comparison surface: <architecture/workflow/tests/report/skill routing/code taste>
- Source evidence to inspect first: <files>
- Current target entrypoints: <files>
- Borrowing matrix candidates: <1-3 concise bullets>
- Preferred adaptation: <smallest patch worth landing now>
- Validation plan: <focused tests/commands>
- Non-goals: <what must not be copied>

# Iteration Loop

1. Start with comparative analysis only; do not edit while the fit is still ambiguous.
2. Promote only one candidate into code at a time.
3. After validation, update the borrowing ledger:
   - accepted borrowing
   - rejected borrowing
   - deferred borrowing
   - next candidate
4. If the same type of comparison repeats across tasks, update this skill's topics, prompt template, or workflow so future routing and execution improve.
5. Prefer reusable heuristics over source-project trivia. The skill should capture the method, not just one case study.

# Output Contract

- Structured comparison summary: 3-6 flat points
- Evidence checklist with exact source and target artifacts
- Borrowing matrix for the shortlisted ideas
- Borrowing ledger with accepted, rejected, and deferred ideas
- Chosen adaptation with exact target files
- Validation evidence
- Next iteration candidate if more borrowing work is justified
