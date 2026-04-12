from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest

from ace_lite.pipeline.stages.skills import (
    extract_error_keywords,
    infer_intent,
    infer_module,
    route_skills,
    run_skills,
)
from ace_lite.pipeline.types import StageContext
from ace_lite.skills import (
    build_skill_catalog,
    build_skill_manifest,
    lint_skill_manifest,
    load_sections,
    select_skills,
)


def _repo_skill_manifest() -> list[dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[2]
    manifest = build_skill_manifest(repo_root / "skills")
    assert manifest
    return manifest


def _select_repo_skill_names(query: str, *, top_n: int = 1) -> list[str]:
    manifest = _repo_skill_manifest()
    query_ctx = {
        "query": query,
        "intent": infer_intent(query),
        "module": "",
        "error_keywords": extract_error_keywords(query),
    }
    selected = select_skills(query_ctx, manifest, top_n=top_n)
    return [str(item["name"]) for item in selected]


def test_build_manifest_and_select(fake_skill_manifest: list[dict[str, Any]]) -> None:
    manifest = fake_skill_manifest
    assert len(manifest) == 2
    assert manifest[0]["name"] == "mem0-codex-playbook"

    selected = select_skills(
        {
            "query": "fix openmemory 405 issue",
            "intent": "memory",
            "module": "mcp",
            "error_keywords": ["405"],
        },
        manifest,
        top_n=1,
    )
    assert len(selected) == 1
    assert selected[0]["name"] == "mem0-codex-playbook"
    assert selected[0]["score"] >= 9


def test_build_skill_catalog_renders_manifest_metadata() -> None:
    catalog = build_skill_catalog(
        [
            {
                "name": "cross-project-borrowing-and-adaptation",
                "path": "skills/cross-project-borrowing-and-adaptation.md",
                "description": "Borrow small, high-value patterns from a reference repo.",
                "intents": ["research", "review"],
                "modules": ["architecture", "docs"],
                "topics": ["compare", "borrow"],
                "default_sections": ["Workflow", "Borrowing Matrix"],
                "priority": 2,
                "token_estimate": 540,
            }
        ]
    )

    assert "# ACE-Lite Skill Catalog" in catalog
    assert "## cross-project-borrowing-and-adaptation" in catalog
    assert "`skills/cross-project-borrowing-and-adaptation.md`" in catalog
    assert "- **Intents:** research, review" in catalog
    assert "- **Default sections:** Workflow, Borrowing Matrix" in catalog
    assert "- **Token estimate:** 540" in catalog


def test_build_skill_catalog_handles_empty_manifest() -> None:
    catalog = build_skill_catalog([])
    assert catalog.startswith("# ACE-Lite Skill Catalog")
    assert "_No skills discovered._" in catalog


def test_load_sections_by_heading(tmp_path: Path) -> None:
    skill_file = tmp_path / "skill.md"
    skill_file.write_text(
        textwrap.dedent(
            """
            ---
            name: sample
            ---
            # Intro
            Alpha

            # Usage
            Beta
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    sections = load_sections(skill_file, ["Usage"])
    assert list(sections.keys()) == ["Usage"]
    assert "Beta" in sections["Usage"]


def test_build_manifest_estimates_token_cost_when_missing(tmp_path: Path) -> None:
    skill_file = tmp_path / "skill.md"
    skill_file.write_text(
        textwrap.dedent(
            """
            ---
            name: sample-skill
            description: sample
            default_sections: [Workflow]
            ---
            # Workflow
            This section has enough words to produce a non-zero token estimate.

            # Extra
            Extra details should not be required for the default estimate.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    manifest = build_skill_manifest(tmp_path)
    assert manifest
    assert int(manifest[0]["token_estimate"] or 0) > 0


def test_build_manifest_keeps_metadata_only_mode_when_budget_fields_exist(
    tmp_path: Path,
) -> None:
    skill_file = tmp_path / "skill.md"
    skill_file.write_text(
        textwrap.dedent(
            """
            ---
            name: sample-skill
            description: sample
            default_sections: [Workflow]
            token_estimate: 128
            ---
            # Workflow
            This section should not be parsed into headings during manifest load.

            # Extra
            This heading is only needed during later hydration.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    manifest = build_skill_manifest(tmp_path)
    assert manifest
    assert manifest[0]["manifest_load_mode"] == "metadata_only"
    assert manifest[0]["headings"] == []


def test_extract_error_keywords_keeps_builtin_lexicon_only() -> None:
    query = "fix anr and crash in android service"
    assert extract_error_keywords(query) == []


def test_extract_error_keywords_supports_chinese_terms() -> None:
    query = "修复维度不匹配和超时错误"
    assert extract_error_keywords(query) == ["不匹配", "维度", "超时", "错误"]


def test_select_skills_matches_manifest_specific_error_keywords_from_query_text() -> None:
    manifest = [
        {
            "name": "android-audio",
            "path": "skills/android.md",
            "description": "android audio troubleshooting",
            "intents": ["troubleshoot"],
            "modules": ["musicservice", "playback"],
            "error_keywords": ["anr", "nullpointer"],
            "topics": ["android", "audio"],
            "default_sections": [],
            "priority": 2,
            "token_estimate": 150,
        }
    ]
    selected = select_skills(
        {
            "query": "fix anr in android musicservice playback",
            "intent": "troubleshoot",
            "module": "",
            "error_keywords": extract_error_keywords("fix anr in android musicservice playback"),
        },
        manifest,
        top_n=1,
    )
    assert selected
    assert selected[0]["name"] == "android-audio"
    assert "error:anr" in selected[0]["matched"]


def test_extract_error_keywords_supports_utf8_chinese_terms() -> None:
    query = "修复维度不匹配和超时错误"
    keywords = extract_error_keywords(query)
    assert "不匹配" in keywords
    assert "维度" in keywords
    assert "超时" in keywords
    assert "错误" in keywords


def test_error_keyword_phrase_requires_exact_match() -> None:
    manifest = [
        {
            "name": "exact-match",
            "path": "skills/exact.md",
            "description": "memory mismatch handling",
            "intents": ["memory"],
            "modules": [],
            "error_keywords": ["mismatch"],
            "topics": [],
            "default_sections": [],
            "priority": 1,
        },
        {
            "name": "phrase-only",
            "path": "skills/phrase.md",
            "description": "context mismatch handoff",
            "intents": ["memory"],
            "modules": [],
            "error_keywords": ["context mismatch"],
            "topics": [],
            "default_sections": [],
            "priority": 1,
        },
    ]
    selected = select_skills(
        {
            "query": "memory mismatch",
            "intent": "memory",
            "module": "",
            "error_keywords": ["mismatch"],
        },
        manifest,
        top_n=2,
    )
    assert [item["name"] for item in selected] == ["exact-match"]


def test_lint_skill_manifest_flags_workflow_error_keywords() -> None:
    issues = lint_skill_manifest(
        [
            {
                "name": "bad-skill",
                "path": "skills/bad.md",
                "intents": ["review"],
                "modules": ["docs"],
                "topics": ["handoff"],
                "error_keywords": ["handoff", "review", "docs"],
            }
        ]
    )
    assert {item["keyword"] for item in issues} == {"handoff", "review", "docs"}


def test_lint_skill_manifest_flags_missing_frontmatter_before_backfill(
    tmp_path: Path,
) -> None:
    (tmp_path / "needs-metadata.md").write_text(
        textwrap.dedent(
            """
            ---
            name: needs-metadata
            description: sample
            ---
            # Workflow
            Missing explicit default sections and token estimate.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    manifest = build_skill_manifest(tmp_path)
    issues = lint_skill_manifest(manifest)

    assert {item["field"] for item in issues} == {
        "default_sections",
        "token_estimate",
    }


def test_lint_skill_manifest_flags_mojibake_metadata_terms() -> None:
    suspicious_one = "".join(chr(code) for code in (0x7035, 0x89C4, 0x7233))
    suspicious_two = "".join(chr(code) for code in (0x934A, 0x7199, 0x58CC))
    issues = lint_skill_manifest(
        [
            {
                "name": "cross-project-borrowing-and-adaptation",
                "path": "skills/cross-project-borrowing-and-adaptation.md",
                "description": "borrow patterns from external repos",
                "intents": ["research"],
                "modules": ["architecture"],
                "topics": ["graphify", suspicious_one, suspicious_two],
                "error_keywords": [],
            }
        ]
    )
    assert len(issues) == 2
    assert {item["field"] for item in issues} == {"topics"}
    assert {item["keyword"] for item in issues} == {suspicious_one, suspicious_two}


def test_repo_skills_pass_frontmatter_lint() -> None:
    issues = lint_skill_manifest(_repo_skill_manifest())
    assert issues == []


def test_select_skills_matches_non_ascii_topic_phrases() -> None:
    manifest = [
        {
            "name": "memory-cn",
            "path": "skills/memory-cn.md",
            "description": "memory review loop",
            "intents": ["memory"],
            "modules": [],
            "error_keywords": [],
            "topics": ["记忆", "检索质量", "噪声"],
            "default_sections": [],
            "priority": 1,
            "token_estimate": 100,
        }
    ]
    selected = select_skills(
        {
            "query": "记忆检索质量优化要先看噪声",
            "intent": "memory",
            "module": "",
            "error_keywords": extract_error_keywords("记忆检索质量优化要先看噪声"),
        },
        manifest,
        top_n=1,
    )
    assert selected
    assert selected[0]["name"] == "memory-cn"
    assert "query_topic_phrases:3" in selected[0]["matched"]


def test_generic_query_without_non_intent_signal_selects_no_skills() -> None:
    manifest = _repo_skill_manifest()
    query = "implement csv export for invoice dashboard widget"
    selected = select_skills(
        {
            "query": query,
            "intent": infer_intent(query),
            "module": "",
            "error_keywords": extract_error_keywords(query),
        },
        manifest,
        top_n=3,
    )
    assert selected == []


def test_run_skills_allows_empty_selection(
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    ctx = StageContext(
        query="implement csv export for invoice dashboard widget",
        repo="demo",
        root=".",
        state={"index": {"module_hint": ""}},
    )
    payload = run_skills(ctx=ctx, skill_manifest=fake_skill_manifest)
    assert payload["query_ctx"]["intent"] == "implement"
    assert payload["available_count"] == len(fake_skill_manifest)
    assert payload["selected_token_estimate_total"] == 0
    assert payload["selected"] == []


def test_run_skills_exposes_selected_token_estimates(
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    ctx = StageContext(
        query="fix openmemory 405 issue",
        repo="demo",
        root=".",
        state={"index": {"module_hint": "infra.mcp"}},
    )
    payload = run_skills(ctx=ctx, skill_manifest=fake_skill_manifest)
    assert payload["selected"]
    assert payload["routing_mode"] == "metadata_only"
    assert payload["metadata_only_routing"] is True
    assert payload["route_latency_ms"] >= 0.0
    assert payload["hydration_latency_ms"] >= 0.0
    assert payload["hydrated_skill_count"] == len(payload["selected"])
    assert payload["selected"][0]["estimated_tokens"] > 0
    assert payload["selected_token_estimate_total"] >= payload["selected"][0]["estimated_tokens"]


def test_run_skills_enforces_token_budget(
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    ctx = StageContext(
        query="fix openmemory 405 issue",
        repo="demo",
        root=".",
        state={"index": {"module_hint": "infra.mcp"}},
    )
    payload = run_skills(
        ctx=ctx,
        skill_manifest=fake_skill_manifest,
        token_budget=1,
    )
    assert payload["selected"] == []
    assert payload["budget_exhausted"] is True
    assert payload["token_budget"] == 1
    assert payload["token_budget_used"] == 0
    assert payload["skipped_for_budget"]


def test_run_skills_can_reuse_precomputed_route(
    fake_skill_manifest: list[dict[str, Any]],
) -> None:
    routed = route_skills(
        query="fix openmemory 405 issue",
        module_hint="infra.mcp",
        skill_manifest=fake_skill_manifest,
        top_n=1,
    )
    ctx = StageContext(
        query="fix openmemory 405 issue",
        repo="demo",
        root=".",
        state={"index": {"module_hint": "infra.mcp"}},
    )
    payload = run_skills(
        ctx=ctx,
        skill_manifest=fake_skill_manifest,
        routed_payload=routed,
        token_budget=999,
    )
    assert payload["routing_source"] == "precomputed"
    assert payload["metadata_only_routing"] is True
    assert payload["route_latency_ms"] == pytest.approx(
        float(routed.get("route_latency_ms", 0.0) or 0.0)
    )
    assert payload["selected"]
    assert payload["selected"][0]["name"] == routed["selected"][0]["name"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("need cross-agent handoff with context sync for the next session", "handoff"),
        ("run release freeze review for the next rc build", "release"),
        ("benchmark tuning should improve latency and recall", "benchmark"),
        ("analyze graphify architecture and borrow workflow ideas", "research"),
        ("refactor duplicated wallet formatting code", "refactor"),
        ("review the schema migration risk", "review"),
        ("search memory context from openmemory", "memory"),
    ],
)
def test_infer_intent_supports_specialized_labels(query: str, expected: str) -> None:
    assert infer_intent(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("交接一下上下文并准备下次续接", "handoff"),
        ("发布前做一次兼容性检查", "release"),
        ("做一轮基准调优看召回和延迟", "benchmark"),
        ("重构重复代码但不要改行为", "refactor"),
        ("记忆检索质量优化", "memory"),
        ("修复超时错误", "troubleshoot"),
    ],
)
def test_infer_intent_supports_chinese_labels(query: str, expected: str) -> None:
    assert infer_intent(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("analyze graphify architecture and borrow workflow ideas", "research"),
        ("compare a reference implementation and adapt the best-fit pattern", "research"),
        ("分析 graphify 架构并借鉴流程设计", "research"),
    ],
)
def test_infer_intent_supports_research_labels(query: str, expected: str) -> None:
    assert infer_intent(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("交接一下上下文并准备下次续接", "handoff"),
        ("分析 graphify 架构并借鉴流程设计", "research"),
        ("重构重复代码但不要改行为", "refactor"),
    ],
)
def test_infer_intent_supports_utf8_chinese_labels(query: str, expected: str) -> None:
    assert infer_intent(query) == expected


def test_infer_module_keeps_nested_segments() -> None:
    assert (
        infer_module(r"src/ace_lite/pipeline/stages/skills.py")
        == "src.ace_lite.pipeline.stages.skills"
    )


def test_cross_agent_skill_routing_prefers_expected_top1() -> None:
    manifest = _repo_skill_manifest()
    cases = [
        (
            "cross-agent-intake-and-scope",
            "Before coding in {agent_name}, define scope, constraints, and validation plan for frontend router cleanup.",
        ),
        (
            "cross-agent-bugfix-and-regression",
            "In {agent_name}, fix failing frontend test with exception and regression in transaction details route and provide rollback plan.",
        ),
        (
            "cross-agent-refactor-safeguards",
            "Use {agent_name} to refactor duplicated wallet table formatting code for maintainability without changing API behavior.",
        ),
        (
            "cross-agent-release-readiness",
            "Run release readiness review in {agent_name} for frontend RC with freeze gates and compatibility checks.",
        ),
        (
            "cross-agent-benchmark-tuning-loop",
            "In {agent_name}, review benchmark tuning loop to improve precision and noise while keeping latency threshold stable.",
        ),
        (
            "cross-agent-handoff-and-context-sync",
            "Create handoff context sync for {agent_name} workflow to avoid stale drift and mismatch next session.",
        ),
    ]

    apps = ("Codex", "OpenCode", "Claude Code")
    for app_name in apps:
        for expected_name, query_template in cases:
            query = query_template.format(agent_name=app_name)
            query_ctx = {
                "query": query,
                "intent": infer_intent(query),
                "module": "",
                "error_keywords": extract_error_keywords(query),
            }
            selected = select_skills(query_ctx, manifest, top_n=1)
            assert selected, f"no skill selected for query: {query}"
            assert (
                selected[0]["name"] == expected_name
            ), f"unexpected top-1 skill for query: {query}; got {selected[0]['name']}"


def test_handoff_query_outranks_benchmark_when_intent_is_handoff() -> None:
    manifest = _repo_skill_manifest()
    query = "need cross-agent handoff after benchmark tuning session"
    selected = select_skills(
        {
            "query": query,
            "intent": infer_intent(query),
            "module": "",
            "error_keywords": extract_error_keywords(query),
        },
        manifest,
        top_n=1,
    )
    assert infer_intent(query) == "handoff"
    assert selected
    assert selected[0]["name"] == "cross-agent-handoff-and-context-sync"


def test_duplication_query_routes_to_refactor_skill() -> None:
    manifest = _repo_skill_manifest()
    query = "resolve duplicated renderer logic without behavior change"
    selected = select_skills(
        {
            "query": query,
            "intent": infer_intent(query),
            "module": "",
            "error_keywords": extract_error_keywords(query),
        },
        manifest,
        top_n=1,
    )
    assert infer_intent(query) == "refactor"
    assert selected
    assert selected[0]["name"] == "cross-agent-refactor-safeguards"


def test_cross_project_borrowing_skill_routes_external_analysis_queries() -> None:
    manifest = _repo_skill_manifest()
    cases = [
        "Analyze graphify architecture and borrow one workflow idea into ace-lite with a minimal validated patch",
        "Compare an external reference repo against the current project, extract inspiration, and adapt the best-fit idea safely",
        "分析 graphify 架构设计并借鉴一条可落地的流程优化到当前项目",
    ]

    for query in cases:
        query_ctx = {
            "query": query,
            "intent": infer_intent(query),
            "module": "",
            "error_keywords": extract_error_keywords(query),
        }
        selected = select_skills(query_ctx, manifest, top_n=1)
        assert selected, f"no skill selected for query: {query}"
        assert (
            selected[0]["name"] == "cross-project-borrowing-and-adaptation"
        ), f"unexpected top-1 skill for query: {query}; got {selected[0]['name']}"


def test_module_hint_promotes_mem0_skill() -> None:
    manifest = _repo_skill_manifest()
    query = "stabilize bridge client after reconnect"
    selected = select_skills(
        {
            "query": query,
            "intent": infer_intent(query),
            "module": infer_module("infra.openmemory.mcp.bridge"),
            "error_keywords": extract_error_keywords(query),
        },
        manifest,
        top_n=1,
    )
    assert selected
    assert selected[0]["name"] == "mem0-codex-playbook"


def test_run_skills_routes_chinese_memory_quality_query_end_to_end() -> None:
    manifest = _repo_skill_manifest()
    ctx = StageContext(
        query="记忆检索质量优化",
        repo="ace-lite-engine",
        root=".",
        state={"index": {"module_hint": ""}},
    )
    payload = run_skills(ctx=ctx, skill_manifest=manifest)
    assert payload["query_ctx"]["error_keywords"] == []
    assert payload["selected"]
    assert payload["selected"][0]["name"] == "mem0-iteration-loop"


def test_ace_dev_skill_routes_ace_lite_operations() -> None:
    manifest = _repo_skill_manifest()
    cases = [
        "Use ace_plan_quick to narrow ace-lite candidate files before a deeper search",
        "Refresh the context-map index with ace_index after changing ace-lite planning heuristics",
        "Escalate from ace_plan_quick to ace_plan for chunk-level ACE-Lite evidence",
        "Search prior ACE-Lite notes with ace_memory_search and persist a stable rule with ace_memory_store",
        "Build a structural dependency map with ace_repomap_build before changing ace-lite retrieval logic",
        "Capture trace_export artifacts and plan_replay_cache behavior while debugging ace-lite config drift",
        "Inspect metadata_only_routing, selected_manifest_token_estimate_total, and hydrated_skill_count before changing ace-lite skills routing",
        "Compare prompt_rendering_boundary_v1, chunk_contract, and subgraph_payload before editing ace-lite source-plan rendering",
    ]

    for query in cases:
        query_ctx = {
            "query": query,
            "intent": infer_intent(query),
            "module": "",
            "error_keywords": extract_error_keywords(query),
        }
        selected = select_skills(query_ctx, manifest, top_n=1)
        assert selected, f"no skill selected for query: {query}"
        assert (
            selected[0]["name"] == "ace-dev"
        ), f"unexpected top-1 skill for query: {query}; got {selected[0]['name']}"


def test_primary_skill_text_is_clean_and_scoped() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    ace_dev_text = (repo_root / "skills" / "ace-dev.md").read_text(encoding="utf-8")
    assert ace_dev_text.isascii()
    assert "ace_plan_quick" in ace_dev_text
    assert "ace_repomap_build" in ace_dev_text
    assert "ace_feedback_stats" in ace_dev_text
    assert "trace_export" in ace_dev_text
    assert "plan_replay_cache" in ace_dev_text
    assert "--trace-export-path" in ace_dev_text
    assert "--output-json" in ace_dev_text
    assert "metadata_only_routing" in ace_dev_text
    assert "selected_manifest_token_estimate_total" in ace_dev_text
    assert "prompt_rendering_boundary_v1" in ace_dev_text
    assert "chunk_contract" in ace_dev_text
    assert "subgraph_payload" in ace_dev_text
    assert "ace-lite runtime doctor-mcp" in ace_dev_text
    assert "Scenario Templates" in ace_dev_text
    assert "Trace-only diagnosis" in ace_dev_text
    assert "Failed-test triage" in ace_dev_text
    assert "Skills-routing budget diagnosis" in ace_dev_text
    assert "Prompt boundary contract check" in ace_dev_text

    manifest = _repo_skill_manifest()
    assert "ace-dev-flac-music-android-kotlin" not in {
        item["name"] for item in manifest
    }

    mem0_text = (
        repo_root / "skills" / "mem0-codex-playbook.md"
    ).read_text(encoding="utf-8")
    assert "bridge" in mem0_text.lower()
    assert "dimension mismatch" in mem0_text.lower()
    assert "memory lifecycle" in mem0_text.lower()
    assert "--memory-primary rest" in mem0_text
    assert "Scenario Templates" in mem0_text
    assert "Noisy retrieval cleanup" in mem0_text

    benchmark_text = (
        repo_root / "skills" / "cross-agent-benchmark-tuning-loop.md"
    ).read_text(encoding="utf-8")
    assert "adaptive_router_mode" in benchmark_text
    assert "trace_export_enabled" in benchmark_text
    assert "plan_replay_cache" in benchmark_text
    assert "Artifact Checklist" in benchmark_text
    assert "validation_result_v1" in benchmark_text
    assert "agent_loop_summary_v1" in benchmark_text
    assert "run_skill_validation.py" in benchmark_text
    assert "skill_validation_matrix.json" in benchmark_text

    release_text = (
        repo_root / "skills" / "cross-agent-release-readiness.md"
    ).read_text(encoding="utf-8")
    assert "junit_xml" in release_text
    assert "sbfl_metric" in release_text
    assert "trace_export_path" in release_text
    assert "--junit-xml" in release_text
    assert "Scenario Templates" in release_text
    assert "RC dry run" in release_text
    assert "skill_validation_matrix" in release_text

    bugfix_text = (
        repo_root / "skills" / "cross-agent-bugfix-and-regression.md"
    ).read_text(encoding="utf-8")
    assert "--failed-test-report" in bugfix_text
    assert "--scip-provider" in bugfix_text
    assert "verify_version_install_sync()" in bugfix_text
    assert "ace-lite runtime doctor-mcp" in bugfix_text
    assert "Scenario Templates" in bugfix_text
    assert "Timeout or trace incident" in bugfix_text
    assert "Install-drift or MCP incident" in bugfix_text
    assert "超时" in bugfix_text
    assert "回归" in bugfix_text

    intake_text = (
        repo_root / "skills" / "cross-agent-intake-and-scope.md"
    ).read_text(encoding="utf-8")
    assert "Artifact Checklist" in intake_text
    assert "trace_export_path" in intake_text
    assert "skills_token_budget" in intake_text
    assert "metadata_only_routing" in intake_text
    assert "prompt_rendering_boundary_v1" in intake_text
    assert "verify_version_install_sync()" in intake_text
    assert "范围不一致" in intake_text
    assert "约束" in intake_text

    handoff_text = (
        repo_root / "skills" / "cross-agent-handoff-and-context-sync.md"
    ).read_text(encoding="utf-8")
    assert "final_query" in handoff_text
    assert "replay_fingerprint" in handoff_text
    assert "metadata_only_routing" in handoff_text
    assert "prompt_rendering_boundary_v1" in handoff_text
    assert "ace-lite runtime doctor-mcp" in handoff_text
    assert "交接" in handoff_text
    assert "上下文同步" in handoff_text

    refactor_text = (
        repo_root / "skills" / "cross-agent-refactor-safeguards.md"
    ).read_text(encoding="utf-8")
    assert "pipeline_order" in refactor_text
    assert "validation_result_v1" in refactor_text
    assert "agent_loop_summary_v1" in refactor_text
    assert "doctor-mcp" in refactor_text
    assert "selected_manifest_token_estimate_total" in refactor_text
    assert "prompt_rendering_boundary_v1" in refactor_text
    assert "replay_fingerprint" in refactor_text
    assert "重构" in refactor_text
    assert "去重" in refactor_text

    mem0_iteration_text = (
        repo_root / "skills" / "mem0-iteration-loop.md"
    ).read_text(encoding="utf-8")
    assert "Artifact Checklist" in mem0_iteration_text
    assert "embedding model and dimension" in mem0_iteration_text
    assert "噪声" in mem0_iteration_text
    assert "检索质量" in mem0_iteration_text

    borrowing_text = (
        repo_root / "skills" / "cross-project-borrowing-and-adaptation.md"
    ).read_text(encoding="utf-8")
    assert "default_sections: [Workflow, Evidence Checklist, Borrowing Matrix, Borrowing Ledger, Output Contract]" in borrowing_text
    assert "Evidence Checklist" in borrowing_text
    assert "Borrowing Matrix" in borrowing_text
    assert "Borrowing Ledger" in borrowing_text
    assert "reference implementation" in borrowing_text
    assert "minimal validated improvement" in borrowing_text
    assert "accepted borrowing" in borrowing_text
    assert "rejected borrowing" in borrowing_text
    assert "deferred borrowing" in borrowing_text
    assert "next candidate" in borrowing_text
    assert "Source revision" in borrowing_text
    assert "shallow clone" in borrowing_text
    assert "local mirror" in borrowing_text
    assert "source-project-specific registry" in borrowing_text
    assert "Report path" in borrowing_text
    assert "graphify" in borrowing_text.lower()
    assert "对标" in borrowing_text
    assert "借鉴" in borrowing_text
    assert "架构设计" in borrowing_text
    assert "流程设计" in borrowing_text


@pytest.mark.parametrize(
    ("query", "expected_name"),
    [
        ("交接一下上下文并准备下次续接", "cross-agent-handoff-and-context-sync"),
        ("做一轮基准调优看召回和延迟", "cross-agent-benchmark-tuning-loop"),
        ("重构重复代码但不要改行为", "cross-agent-refactor-safeguards"),
        ("发布前做一次兼容性检查", "cross-agent-release-readiness"),
    ],
)
def test_repo_skills_route_chinese_queries(query: str, expected_name: str) -> None:
    manifest = _repo_skill_manifest()
    query_ctx = {
        "query": query,
        "intent": infer_intent(query),
        "module": "",
        "error_keywords": extract_error_keywords(query),
    }
    selected = select_skills(query_ctx, manifest, top_n=1)
    assert selected, f"no skill selected for query: {query}"
    assert selected[0]["name"] == expected_name


def test_repo_skills_all_publish_token_estimates() -> None:
    manifest = _repo_skill_manifest()
    assert manifest
    for item in manifest:
        assert int(item.get("token_estimate") or 0) > 0


def test_cross_agent_benchmark_routes_feedback_queries() -> None:
    manifest = _repo_skill_manifest()
    cases = [
        "Use benchmark tuning to compare precision and noise before rollout",
        "Run benchmark loop and record ace_feedback_record for selected paths",
        "Tune embedding rerank pool and scip provider, then capture trace_export evidence for latency regression review",
        "Benchmark 前先固定 validation 和 agent_loop 状态，并记录 validation_result_v1 与 agent_loop_summary_v1",
        "Benchmark 比较前先固定 validation_tests 和 agent_loop stop_reason，再对照 precision、noise 和 latency",
    ]

    for query in cases:
        query_ctx = {
            "query": query,
            "intent": infer_intent(query),
            "module": "",
            "error_keywords": extract_error_keywords(query),
        }
        selected = select_skills(query_ctx, manifest, top_n=1)
        assert selected, f"no skill selected for query: {query}"
        assert (
            selected[0]["name"] == "cross-agent-benchmark-tuning-loop"
        ), f"unexpected top-1 skill for query: {query}; got {selected[0]['name']}"


def test_cross_agent_refactor_routes_runtime_contract_queries() -> None:
    manifest = _repo_skill_manifest()
    cases = [
        "重构 orchestrator 但保持 validation_result_v1、agent_loop_summary_v1 和 pipeline_order 不变",
        "Refactor runtime CLI without changing doctor output shape or version drift checks",
    ]

    for query in cases:
        query_ctx = {
            "query": query,
            "intent": infer_intent(query),
            "module": "",
            "error_keywords": extract_error_keywords(query),
        }
        selected = select_skills(query_ctx, manifest, top_n=1)
        assert selected, f"no skill selected for query: {query}"
        assert (
            selected[0]["name"] == "cross-agent-refactor-safeguards"
        ), f"unexpected top-1 skill for query: {query}; got {selected[0]['name']}"


def test_cross_agent_release_routes_diagnostics_and_trace_queries() -> None:
    manifest = _repo_skill_manifest()
    query = "Prepare release go-no-go with junit_xml, sbfl_metric, trace_export_path, and scip provider compatibility evidence"
    query_ctx = {
        "query": query,
        "intent": infer_intent(query),
        "module": "",
        "error_keywords": extract_error_keywords(query),
    }
    selected = select_skills(query_ctx, manifest, top_n=1)
    assert selected
    assert selected[0]["name"] == "cross-agent-release-readiness"


def test_cross_agent_bugfix_routes_diagnostics_queries() -> None:
    manifest = _repo_skill_manifest()
    query = "Fix regression using failed_test_report, sbfl_metric, and scip provider evidence before rerunning tests"
    query_ctx = {
        "query": query,
        "intent": infer_intent(query),
        "module": "",
        "error_keywords": extract_error_keywords(query),
    }
    selected = select_skills(query_ctx, manifest, top_n=1)
    assert selected
    assert selected[0]["name"] == "cross-agent-bugfix-and-regression"


def test_cross_agent_intake_routes_config_surface_queries() -> None:
    manifest = _repo_skill_manifest()
    query = "Before coding, scope embeddings, scip, trace_export, chunk_guard, and adaptive_router changes with validation artifacts"
    query_ctx = {
        "query": query,
        "intent": infer_intent(query),
        "module": "",
        "error_keywords": extract_error_keywords(query),
    }
    selected = select_skills(query_ctx, manifest, top_n=1)
    assert selected
    assert selected[0]["name"] == "cross-agent-intake-and-scope"


@pytest.mark.parametrize(
    ("query", "expected_top1"),
    [
        (
            "Prepare handoff with final_query, replay_fingerprint, metadata_only_routing, and prompt_rendering_boundary_v1 snapshot for the next session",
            "cross-agent-handoff-and-context-sync",
        ),
        (
            "Before coding, scope precomputed_skills_routing_enabled, skills_token_budget, metadata_only_routing, and prompt_rendering_boundary_v1 contract",
            "cross-agent-intake-and-scope",
        ),
        (
            "\u8303\u56f4\u4e0d\u4e00\u81f4\uff0c\u9700\u8981\u5148\u89c4\u5212\u7ea6\u675f\u548c\u9a8c\u8bc1\u518d\u6539\u4ee3\u7801",
            "cross-agent-intake-and-scope",
        ),
        (
            "Fix failing test regression after install drift using failed_test_report, verify_version_install_sync(), and ace-lite runtime doctor-mcp before rerunning tests",
            "cross-agent-bugfix-and-regression",
        ),
        (
            "\u4fee\u590d\u8d85\u65f6\u56de\u5f52\u5e76\u5148\u68c0\u67e5 install drift \u548c doctor-mcp",
            "cross-agent-bugfix-and-regression",
        ),
    ],
)
def test_skill_routing_boundary_matrix_top1(query: str, expected_top1: str) -> None:
    selected = _select_repo_skill_names(query, top_n=1)
    assert selected
    assert selected[0] == expected_top1


@pytest.mark.parametrize(
    ("query", "expected_order"),
    [
        (
            "Check install drift with verify_version_install_sync and doctor-mcp for ace-lite after reinstall",
            ["ace-dev", "cross-agent-refactor-safeguards"],
        ),
        (
            "Fix failing test regression after install drift with failed_test_report and doctor-mcp",
            ["cross-agent-bugfix-and-regression", "ace-dev"],
        ),
        (
            "Prepare handoff with prompt_rendering_boundary_v1 and replay_fingerprint",
            ["cross-agent-handoff-and-context-sync", "cross-agent-refactor-safeguards"],
        ),
        (
            "Before coding, scope validation constraints and prompt boundary changes",
            ["cross-agent-intake-and-scope", "ace-dev"],
        ),
    ],
)
def test_skill_routing_boundary_matrix_top2(
    query: str, expected_order: list[str]
) -> None:
    selected = _select_repo_skill_names(query, top_n=len(expected_order))
    assert selected[: len(expected_order)] == expected_order


def test_mem0_skills_route_lifecycle_queries() -> None:
    manifest = _repo_skill_manifest()
    query = "Tune memory_profile, memory_postprocess, and memory_capture before changing openmemory prompts"
    query_ctx = {
        "query": query,
        "intent": infer_intent(query),
        "module": "",
        "error_keywords": extract_error_keywords(query),
    }
    selected = select_skills(query_ctx, manifest, top_n=1)
    assert selected
    assert selected[0]["name"] == "mem0-codex-playbook"
