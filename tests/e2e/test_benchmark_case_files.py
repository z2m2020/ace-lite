from __future__ import annotations

from pathlib import Path

import yaml


def test_recovery_hard_cases_cover_planned_surfaces() -> None:
    config_path = (
        Path(__file__).resolve().parents[2]
        / "benchmark"
        / "cases"
        / "recovery_hard_cases.yaml"
    )
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    assert len(cases) == 4

    case_ids = {str(item.get("case_id") or "") for item in cases if isinstance(item, dict)}
    assert case_ids == {
        "ace-recovery-insufficiency-01",
        "ace-recovery-ambiguity-02",
        "ace-recovery-paraphrase-03",
        "ace-recovery-multifile-04",
    }

    surfaces = {
        str(item.get("recovery_surface") or "")
        for item in cases
        if isinstance(item, dict)
    }
    assert surfaces == {
        "insufficiency",
        "ambiguity",
        "paraphrase_drift",
        "multi_file_recovery",
    }

    insufficiency = next(
        item
        for item in cases
        if isinstance(item, dict)
        and item.get("case_id") == "ace-recovery-insufficiency-01"
    )
    assert insufficiency["comparison_lane"] == "adaptive_recovery"
    assert insufficiency["task_success"] == {
        "mode": "positive",
        "min_validation_tests": 1,
    }


def test_chunking_hard_cases_define_stage_aware_oracles() -> None:
    config_path = (
        Path(__file__).resolve().parents[2]
        / "benchmark"
        / "cases"
        / "chunking_hard_cases.yaml"
    )
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    assert len(cases) == 5

    case_ids = {str(item.get("case_id") or "") for item in cases if isinstance(item, dict)}
    assert case_ids == {
        "ace-chunking-files-01",
        "ace-chunking-raw-chunks-02",
        "ace-chunking-pack-03",
        "ace-chunking-sibling-shield-04",
        "ace-chunking-hub-heavy-05",
    }

    expected_oracles = {
        "ace-chunking-files-01": (
            "src/ace_lite/benchmark/case_evaluation.py",
            "evaluate_case_result",
        ),
        "ace-chunking-raw-chunks-02": (
            "src/ace_lite/benchmark/summaries.py",
            "build_evidence_insufficiency_summary",
        ),
        "ace-chunking-pack-03": (
            "src/ace_lite/benchmark/report.py",
            "_append_evidence_insufficiency_summary",
        ),
        "ace-chunking-sibling-shield-04": (
            "src/ace_lite/chunking/topological_shield.py",
            "compute_topological_shield",
        ),
        "ace-chunking-hub-heavy-05": (
            "src/ace_lite/chunking/graph_prior.py",
            "apply_query_aware_graph_prior",
        ),
    }

    for item in cases:
        case_id = str(item["case_id"])
        assert item["comparison_lane"] == "chunking_hard_cases"
        assert item["oracle_file_path"].startswith("src/ace_lite/")
        assert item["oracle_chunk_ref"]["path"] == item["oracle_file_path"]
        assert (
            item["oracle_file_path"],
            item["oracle_chunk_ref"]["qualified_name"],
        ) == expected_oracles[case_id]


def test_validation_rich_cases_cover_validation_and_agent_loop_surfaces() -> None:
    config_path = (
        Path(__file__).resolve().parents[2]
        / "benchmark"
        / "cases"
        / "validation_rich_cases.yaml"
    )
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    assert len(cases) == 7

    case_ids = {str(item.get("case_id") or "") for item in cases if isinstance(item, dict)}
    assert case_ids == {
        "ace-validation-source-plan-01",
        "ace-validation-stage-sandbox-02",
        "ace-agent-loop-validation-03",
        "ace-runtime-mcp-selftest-04",
        "ace-validation-schema-contract-05",
        "ace-validation-failure-signals-06",
        "ace-validation-release-docs-negative-control-07",
    }

    surfaces = {
        str(item.get("validation_surface") or "")
        for item in cases
        if isinstance(item, dict)
    }
    assert surfaces == {
        "source_plan",
        "validation_stage",
        "agent_loop",
        "runtime_mcp",
        "schema_contract",
        "failure_signals",
        "release_docs_negative_control",
    }

    for item in cases:
        assert item["comparison_lane"] == "validation_rich"
        assert item["task_success"]["min_validation_tests"] == 1
        filters = item["filters"]
        assert filters["exclude_paths"] == [
            "tests/e2e/test_benchmark_case_files.py",
            "tests/e2e/test_full_validation_script.py",
            "tests/e2e/test_run_benchmark_script.py",
            "scripts/metrics_collector.py",
            "scripts/run_release_freeze_regression.py",
            "src/ace_lite/benchmark/case_evaluation.py",
        ]
        assert filters["exclude_globs"] == [
            "scripts/*validation_rich*.py",
            "tests/e2e/test_validation_rich*_script.py",
            "tests/e2e/test_archive_validation_rich_evidence_script.py",
        ]

    negative_control = next(
        item
        for item in cases
        if isinstance(item, dict)
        and item.get("case_id") == "ace-validation-release-docs-negative-control-07"
    )
    assert negative_control["query"] == (
        "where are the maintainer docs for validation-rich release checklist and benchmark gate review"
    )
    assert negative_control["expected_keys"] == [
        "releasing",
        "benchmarking",
        "maintainers",
    ]
    assert negative_control["filters"]["include_globs"] == [
        "docs/maintainers/*.md",
    ]
    assert negative_control["task_success"] == {
        "mode": "negative_control",
        "min_validation_tests": 1,
    }

    runtime_mcp = next(
        item
        for item in cases
        if isinstance(item, dict)
        and item.get("case_id") == "ace-runtime-mcp-selftest-04"
    )
    assert runtime_mcp["filters"]["include_paths"] == [
        "src/ace_lite/cli_app/commands/runtime.py",
        "src/ace_lite/runtime_settings.py",
        "tests/integration/test_cli_runtime.py",
        "tests/unit/test_plugins_runtime.py",
    ]

    source_plan = next(
        item
        for item in cases
        if isinstance(item, dict)
        and item.get("case_id") == "ace-validation-source-plan-01"
    )
    assert source_plan["filters"]["include_paths"] == [
        "src/ace_lite/source_plan/validation_tests.py",
        "src/ace_lite/source_plan/__init__.py",
    ]

    validation_stage = next(
        item
        for item in cases
        if isinstance(item, dict)
        and item.get("case_id") == "ace-validation-stage-sandbox-02"
    )
    assert validation_stage["filters"]["include_paths"] == [
        "src/ace_lite/pipeline/stages/validation.py",
        "src/ace_lite/validation/sandbox.py",
        "src/ace_lite/validation/patch_artifact.py",
        "src/ace_lite/validation/result.py",
        "tests/unit/test_validation_stage.py",
        "tests/unit/test_validation_sandbox.py",
        "tests/unit/test_validation_result.py",
    ]

    agent_loop = next(
        item
        for item in cases
        if isinstance(item, dict)
        and item.get("case_id") == "ace-agent-loop-validation-03"
    )
    assert agent_loop["filters"]["include_paths"] == [
        "src/ace_lite/agent_loop/controller.py",
        "src/ace_lite/agent_loop/contracts.py",
        "src/ace_lite/orchestrator_runtime_support.py",
        "tests/unit/test_agent_loop_controller.py",
        "tests/unit/test_agent_loop_contracts.py",
        "tests/integration/test_orchestrator.py",
    ]

    schema_contract = next(
        item
        for item in cases
        if isinstance(item, dict)
        and item.get("case_id") == "ace-validation-schema-contract-05"
    )
    assert schema_contract["filters"]["include_paths"] == [
        "src/ace_lite/schema.py",
        "src/ace_lite/validation/result.py",
        "tests/unit/test_schema.py",
        "tests/unit/test_validation_result.py",
    ]

    failure_signals = next(
        item
        for item in cases
        if isinstance(item, dict)
        and item.get("case_id") == "ace-validation-failure-signals-06"
    )
    assert failure_signals["filters"]["include_paths"] == [
        "src/ace_lite/benchmark/scoring.py",
        "src/ace_lite/benchmark/case_evaluation_details.py",
        "tests/unit/test_benchmark_scoring.py",
        "tests/unit/test_benchmark_runner.py",
    ]


def test_external_howwhy_matrix_reuses_primary_checkout_names() -> None:
    config_path = (
        Path(__file__).resolve().parents[2]
        / "benchmark"
        / "matrix"
        / "external_howwhy.yaml"
    )
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    repos = payload.get("repos", []) if isinstance(payload, dict) else []
    assert repos
    for item in repos:
        assert item["name"] == item["repo"]


def test_stale_majority_cases_define_explicit_chunk_guard_lane() -> None:
    config_path = (
        Path(__file__).resolve().parents[2]
        / "benchmark"
        / "cases"
        / "stale_majority_cases.yaml"
    )
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    assert len(cases) == 3

    case_ids = {str(item.get("case_id") or "") for item in cases if isinstance(item, dict)}
    assert case_ids == {
        "ace-stale-majority-anchor-01",
        "ace-stale-majority-selection-02",
        "ace-stale-majority-signature-03",
    }

    for item in cases:
        assert item["comparison_lane"] == "stale_majority"
        assert item["oracle_file_path"].startswith("src/ace_lite/")
        assert item["oracle_chunk_ref"]["path"] == item["oracle_file_path"]
        assert item["oracle_chunk_ref"]["qualified_name"]


def test_grpc_java_matrix_cases_cover_java_dependency_heavy_surfaces() -> None:
    config_path = (
        Path(__file__).resolve().parents[2]
        / "benchmark"
        / "cases"
        / "matrix"
        / "grpc_java.yaml"
    )
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    assert len(cases) == 3

    case_ids = {str(item.get("case_id") or "") for item in cases if isinstance(item, dict)}
    assert case_ids == {
        "grpc-java-managed-channel-builder",
        "grpc-java-netty-channel-builder",
        "grpc-java-xds-name-resolver-provider",
    }

    expected_keys = {
        "grpc-java-managed-channel-builder": (
            "api/src/main/java/io/grpc/ManagedChannelBuilder.java",
            "ManagedChannelBuilder",
        ),
        "grpc-java-netty-channel-builder": (
            "netty/src/main/java/io/grpc/netty/NettyChannelBuilder.java",
            "NettyChannelBuilder",
        ),
        "grpc-java-xds-name-resolver-provider": (
            "xds/src/main/java/io/grpc/xds/XdsNameResolverProvider.java",
            "XdsNameResolverProvider",
        ),
    }

    for item in cases:
        case_id = str(item["case_id"])
        assert item["top_k"] == 6
        assert tuple(item["expected_keys"]) == expected_keys[case_id]


def test_feedback_loop_cases_cover_issue_export_and_resolution_surfaces() -> None:
    config_path = (
        Path(__file__).resolve().parents[2]
        / "benchmark"
        / "cases"
        / "feedback_loop_cases.yaml"
    )
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    assert len(cases) == 4

    case_ids = {str(item.get("case_id") or "") for item in cases if isinstance(item, dict)}
    assert case_ids == {
        "ace-feedback-issue-export-cli-01",
        "ace-feedback-issue-export-mcp-02",
        "ace-feedback-resolution-cli-03",
        "ace-feedback-resolution-mcp-04",
    }

    surfaces = {
        str(item.get("feedback_surface") or "")
        for item in cases
        if isinstance(item, dict)
    }
    assert surfaces == {
        "issue_report_export_cli",
        "issue_report_export_mcp",
        "issue_resolution_cli",
        "issue_resolution_mcp",
    }

    expected_lanes = {
        "ace-feedback-issue-export-cli-01": "issue_report_feedback",
        "ace-feedback-issue-export-mcp-02": "issue_report_feedback",
        "ace-feedback-resolution-cli-03": "dev_feedback_resolution",
        "ace-feedback-resolution-mcp-04": "dev_feedback_resolution",
    }
    expected_include_paths = {
        "ace-feedback-issue-export-cli-01": [
            "src/ace_lite/cli_app/commands/feedback.py",
            "src/ace_lite/issue_report_store.py",
            "src/ace_lite/feedback_issue_linkage.py",
            "tests/integration/test_cli_feedback.py",
        ],
        "ace-feedback-issue-export-mcp-02": [
            "src/ace_lite/mcp_server/service_issue_report_handlers.py",
            "src/ace_lite/mcp_server/service.py",
            "src/ace_lite/mcp_server/server_tool_registration.py",
            "src/ace_lite/issue_report_store.py",
            "src/ace_lite/feedback_issue_linkage.py",
            "tests/unit/test_mcp_service_issue_report_handlers.py",
            "tests/unit/test_mcp_server.py",
        ],
        "ace-feedback-resolution-cli-03": [
            "src/ace_lite/cli_app/commands/feedback.py",
            "src/ace_lite/issue_report_store.py",
            "src/ace_lite/dev_feedback_store.py",
            "src/ace_lite/feedback_issue_linkage.py",
            "tests/integration/test_cli_feedback.py",
        ],
        "ace-feedback-resolution-mcp-04": [
            "src/ace_lite/mcp_server/service_issue_report_handlers.py",
            "src/ace_lite/mcp_server/service.py",
            "src/ace_lite/mcp_server/server_tool_registration.py",
            "src/ace_lite/issue_report_store.py",
            "src/ace_lite/dev_feedback_store.py",
            "src/ace_lite/feedback_issue_linkage.py",
            "tests/unit/test_mcp_service_issue_report_handlers.py",
            "tests/unit/test_mcp_server.py",
        ],
    }
    expected_dev_feedback = {
        "ace-feedback-resolution-cli-03": {
            "issue_count": 1,
            "linked_fix_issue_count": 1,
            "resolved_issue_count": 1,
        },
        "ace-feedback-resolution-mcp-04": {
            "issue_count": 1,
            "linked_fix_issue_count": 1,
            "resolved_issue_count": 1,
        },
    }

    for item in cases:
        case_id = str(item["case_id"])
        assert item["comparison_lane"] == expected_lanes[case_id]
        assert item["top_k"] == 8
        assert item["task_success"] == {
            "mode": "positive",
            "min_validation_tests": 1,
        }
        assert item["filters"]["include_paths"] == expected_include_paths[case_id]
        if case_id in expected_dev_feedback:
            assert item["dev_feedback"] == expected_dev_feedback[case_id]


def test_memory_feedback_cases_cover_memory_taxonomy_surfaces() -> None:
    config_path = (
        Path(__file__).resolve().parents[2]
        / "benchmark"
        / "cases"
        / "memory_feedback_cases.yaml"
    )
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    assert len(cases) == 5

    case_ids = {str(item.get("case_id") or "") for item in cases if isinstance(item, dict)}
    assert case_ids == {
        "ace-memory-neutral-routing-01",
        "ace-memory-helpful-ltm-02",
        "ace-memory-harmful-negative-control-03",
        "ace-memory-time-sensitive-asof-04",
        "ace-memory-cross-session-recovery-05",
    }

    surfaces = {
        str(item.get("memory_surface") or "")
        for item in cases
        if isinstance(item, dict)
    }
    assert surfaces == {
        "namespace_routing",
        "ltm_plan_attribution",
        "docs_negative_control",
        "as_of_boundary",
        "feedback_recovery",
    }

    expected_lanes = {
        "ace-memory-neutral-routing-01": "memory-neutral",
        "ace-memory-helpful-ltm-02": "memory-helpful",
        "ace-memory-harmful-negative-control-03": "memory-harmful-negative-control",
        "ace-memory-time-sensitive-asof-04": "time-sensitive",
        "ace-memory-cross-session-recovery-05": "cross-session-recovery",
    }

    for item in cases:
        case_id = str(item["case_id"])
        assert item["comparison_lane"] == expected_lanes[case_id]
        assert item["top_k"] == 8
        assert item["task_success"]["min_validation_tests"] == 1

    negative_control = next(
        item
        for item in cases
        if isinstance(item, dict)
        and item.get("case_id") == "ace-memory-harmful-negative-control-03"
    )
    assert negative_control["task_success"] == {
        "mode": "negative_control",
        "min_validation_tests": 1,
    }
    assert negative_control["filters"]["include_globs"] == [
        "docs/maintainers/*.md",
        "docs/reference/*.md",
    ]

    helpful = next(
        item
        for item in cases
        if isinstance(item, dict)
        and item.get("case_id") == "ace-memory-helpful-ltm-02"
    )
    assert helpful["filters"]["include_paths"] == [
        "src/ace_lite/pipeline/stages/memory.py",
        "src/ace_lite/pipeline/stages/source_plan.py",
        "src/ace_lite/benchmark/case_evaluation_metrics.py",
        "src/ace_lite/benchmark/case_evaluation_row.py",
        "tests/unit/test_source_plan_properties.py",
        "tests/unit/test_benchmark_scoring.py",
    ]

