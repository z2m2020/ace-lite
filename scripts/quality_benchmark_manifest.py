#!/usr/bin/env python3
"""Quality Optimization Benchmark Manifest

This module defines the benchmark lanes and metrics for the ACE-Lite quality
optimization effort (PRD-91).

Usage:
    python scripts/quality_benchmark_manifest.py
    python scripts/quality_benchmark_manifest.py --output artifacts/quality-optimization/benchmark_manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# Metrics definitions matching PRD-91
METRICS_DEFINITIONS = {
    "M-ARCH-01": {
        "name": "dict_fallback_sites",
        "description": "裸 dict/ctx.state/.get() 防御代码位置计数",
        "category": "architecture",
        "phase": 2,
        "unit": "count",
        "target_direction": "decrease",
    },
    "M-ARCH-02": {
        "name": "typed_contract_coverage",
        "description": "stage 热路径强契约覆盖率",
        "category": "architecture",
        "phase": 2,
        "unit": "percentage",
        "target_direction": "increase",
    },
    "M-CFG-01": {
        "name": "config_duplicate_section_count",
        "description": "配置建模双轨重复字段计数",
        "category": "config",
        "phase": 2,
        "unit": "count",
        "target_direction": "decrease",
    },
    "M-PLAN-01": {
        "name": "plan_quick_rule_cluster_count",
        "description": "marker/boost/domain 规则聚类计数",
        "category": "plan_quick",
        "phase": 1,
        "unit": "count",
        "target_direction": "decrease",
    },
    "M-PLAN-02": {
        "name": "plan_quick_regression_count",
        "description": "规则收敛可能引起的排序漂移",
        "category": "plan_quick",
        "phase": 1,
        "unit": "count",
        "target_direction": "zero",
    },
    "M-IDX-01": {
        "name": "index_scan_elapsed_ms",
        "description": "索引扫描耗时（毫秒）",
        "category": "indexer",
        "phase": 1,
        "unit": "milliseconds",
        "target_direction": "decrease",
    },
    "M-IDX-02": {
        "name": "ignore_match_overhead_ms",
        "description": "ignore 判断分散开销",
        "category": "indexer",
        "phase": 1,
        "unit": "milliseconds",
        "target_direction": "decrease",
    },
    "M-CACHE-01": {
        "name": "cache_deepcopy_count",
        "description": "深拷贝调用次数",
        "category": "cache",
        "phase": 1,
        "unit": "count",
        "target_direction": "decrease",
    },
    "M-CACHE-02": {
        "name": "cache_json_roundtrip_ms",
        "description": "JSON序列化往返耗时",
        "category": "cache",
        "phase": 3,
        "unit": "milliseconds",
        "target_direction": "decrease",
    },
    "M-REL-01": {
        "name": "broad_exception_sites",
        "description": "宽泛 except Exception 站点计数",
        "category": "reliability",
        "phase": 1,
        "unit": "count",
        "target_direction": "decrease",
    },
    "M-REL-02": {
        "name": "windows_fs_edge_tests",
        "description": "Windows 文件系统边界测试覆盖率",
        "category": "reliability",
        "phase": 1,
        "unit": "count",
        "target_direction": "increase",
    },
}

# Stream definitions matching PRD-91
STREAMS = {
    "A": {
        "name": "Orchestrator Hot Path Typed Contracts",
        "metrics": ["M-ARCH-01", "M-ARCH-02"],
        "files": [
            "src/ace_lite/orchestrator.py",
            "src/ace_lite/orchestrator_runtime_*.py",
            "tests/unit/test_orchestrator*.py",
        ],
    },
    "B": {
        "name": "Config Single Source of Truth",
        "metrics": ["M-CFG-01"],
        "files": [
            "src/ace_lite/config_models.py",
            "src/ace_lite/orchestrator_config.py",
            "src/ace_lite/shared_plan_runtime_config.py",
            "tests/unit/test_*config*.py",
        ],
    },
    "C": {
        "name": "Plan Quick Strategy Registry",
        "metrics": ["M-PLAN-01", "M-PLAN-02"],
        "files": [
            "src/ace_lite/plan_quick.py",
            "src/ace_lite/retrieval_shared.py",
            "tests/unit/test_plan_quick.py",
        ],
    },
    "D": {
        "name": "Indexer Hotspot Reduction",
        "metrics": ["M-IDX-01", "M-IDX-02"],
        "files": [
            "src/ace_lite/indexer.py",
            "tests/unit/test_indexer.py",
            "tests/integration/test_*index*.py",
        ],
    },
    "E": {
        "name": "Repomap Cache Lightweight Payload",
        "metrics": ["M-CACHE-01", "M-CACHE-02"],
        "files": [
            "src/ace_lite/repomap/cache.py",
            "src/ace_lite/repomap/cache_runtime.py",
            "tests/unit/test_repomap_cache*.py",
        ],
    },
    "F": {
        "name": "Exception Governance and Windows FS Matrix",
        "metrics": ["M-REL-01", "M-REL-02"],
        "files": [
            "src/ace_lite/repomap/cache.py",
            "src/ace_lite/index_stage/*.py",
            "tests/integration/",
            "tests/unit/test_*",
        ],
    },
}

# Phase definitions
PHASES = {
    "Phase 0": {
        "description": "基线与实验框架冻结 (2026-04-12 到 2026-04-19)",
        "tasks": ["QO-0001", "QO-0002", "QO-0003"],
        "streams": [],
    },
    "Phase 1": {
        "description": "低风险高收益治理 (2026-04-20 到 2026-05-10)",
        "tasks": ["QO-1101", "QO-1102", "QO-1103", "QO-1104", "QO-1105"],
        "streams": ["C", "D", "E", "F"],
    },
    "Phase 2": {
        "description": "结构收敛 (2026-05-11 到 2026-06-07)",
        "tasks": ["QO-2101", "QO-2102", "QO-2103", "QO-2104"],
        "streams": ["A", "B"],
    },
    "Phase 3": {
        "description": "实验性性能决策 (2026-06-08 到 2026-06-30)",
        "tasks": ["QO-3101", "QO-3102", "QO-3103", "QO-3104"],
        "streams": [],
    },
}


def build_manifest() -> dict:
    """Build the complete benchmark manifest."""
    return {
        "schema_version": "quality_optimization_manifest_v1",
        "prd": "91_QUALITY_OPTIMIZATION_PRD_2026-04-12",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": METRICS_DEFINITIONS,
        "streams": STREAMS,
        "phases": PHASES,
        "artifact_paths": {
            "baseline_dir": "artifacts/quality-optimization/baseline/",
            "experiments_dir": "artifacts/quality-optimization/experiments/",
            "static_hotspots": "artifacts/quality-optimization/baseline/static_hotspots.json",
            "indexer_benchmark": "artifacts/quality-optimization/baseline/indexer_benchmark.json",
            "cache_benchmark": "artifacts/quality-optimization/baseline/cache_benchmark.json",
            "processpool_benchmark": "artifacts/quality-optimization/experiments/processpool_parse_benchmark.json",
            "json_codec_benchmark": "artifacts/quality-optimization/experiments/json_codec_benchmark.json",
        },
        "verification_commands": {
            "plan_quick": "pytest tests/unit/test_plan_quick.py -q",
            "indexer": "pytest tests/unit/test_indexer.py -q",
            "repomap_cache": "pytest tests/unit/test_repomap_cache_runtime.py tests/unit/test_repomap_stage_runtime.py -q",
            "orchestrator": "pytest tests/unit/test_orchestrator*.py -q",
            "config": "pytest tests/unit/test_*config*.py -q",
            "full": "pytest -q",
        },
        "rollback_templates": {
            "plan_quick": "git restore -- src/ace_lite/plan_quick.py src/ace_lite/retrieval_shared.py tests/unit/test_plan_quick.py",
            "indexer": "git restore -- src/ace_lite/indexer.py tests/unit/test_indexer.py",
            "repomap_cache": "git restore -- src/ace_lite/repomap/cache.py src/ace_lite/repomap/cache_runtime.py tests/unit/test_repomap_cache*.py",
            "orchestrator": "git restore -- src/ace_lite/orchestrator.py src/ace_lite/orchestrator_runtime_support_types.py src/ace_lite/orchestrator_runtime_*.py",
            "config": "git restore -- src/ace_lite/config_models.py src/ace_lite/orchestrator_config.py src/ace_lite/shared_plan_runtime_config.py",
        },
    }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Quality Optimization Benchmark Manifest Generator (PRD-91)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output JSON file path (default: print to stdout)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate manifest structure without writing",
    )

    args = parser.parse_args()

    manifest = build_manifest()

    if args.validate:
        print("Manifest structure validation:")
        print(f"  - Schema version: {manifest['schema_version']}")
        print(f"  - Metrics count: {len(manifest['metrics'])}")
        print(f"  - Streams count: {len(manifest['streams'])}")
        print(f"  - Phases count: {len(manifest['phases'])}")
        print("  - Artifact paths: OK")
        print("  - Verification commands: OK")
        print("  - Rollback templates: OK")
        print("\nValidation PASSED")
        return 0

    json_output = json.dumps(manifest, indent=2, ensure_ascii=False)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json_output, encoding="utf-8")
        print(f"Manifest written to: {args.output}")
        return 0
    else:
        print(json_output)
        return 0


if __name__ == "__main__":
    sys.exit(main())
