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
