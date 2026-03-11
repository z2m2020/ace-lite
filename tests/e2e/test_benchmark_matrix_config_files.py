from __future__ import annotations

from pathlib import Path

import yaml


def test_primary_matrix_includes_dependency_heavy_polyglot_targets() -> None:
    config_path = Path(__file__).resolve().parents[2] / "benchmark" / "matrix" / "repos.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    repos = payload.get("repos", []) if isinstance(payload, dict) else []
    names = {str(item.get("name") or "") for item in repos if isinstance(item, dict)}

    assert {"protobuf-go", "grpc-java", "lens-core", "uniswap-v4-core"}.issubset(names)

    grpc_java = next(item for item in repos if item.get("name") == "grpc-java")
    assert grpc_java["languages"] == "java"
    assert grpc_java["cases"] == "benchmark/cases/matrix/grpc_java.yaml"
    assert grpc_java["thresholds"] == {
        "latency_p95_ms_max": 2500.0,
        "dependency_recall_min": 0.85,
    }

    uniswap = next(item for item in repos if item.get("name") == "uniswap-v4-core")
    assert uniswap["languages"] == "solidity"
    assert uniswap["submodules"] == [
        "lib/forge-std",
        "lib/solmate",
        "lib/openzeppelin-contracts",
    ]
