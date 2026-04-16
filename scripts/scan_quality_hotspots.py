#!/usr/bin/env python3
"""Static Hotspot Scanner for Quality Optimization

This module scans the codebase for quality hotspots identified in PRD-91.

Usage:
    python scripts/scan_quality_hotspots.py
    python scripts/scan_quality_hotspots.py --output artifacts/quality-optimization/baseline/static_hotspots.json
    python scripts/scan_quality_hotspots.py --filter M-ARCH-01 --filter M-CACHE-01
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


@dataclass
class HotspotResult:
    """Represents a single hotspot finding."""

    metric_id: str
    file_path: str
    line_number: int
    line_content: str
    pattern: str
    context: str = ""


@dataclass
class ScanResults:
    """Aggregated scan results."""

    metric_id: str
    metric_name: str
    total_count: int
    findings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "metric_id": self.metric_id,
            "metric_name": self.metric_name,
            "total_count": self.total_count,
            "findings": [
                {
                    "file": f.file_path,
                    "line": f.line_number,
                    "content": f.line_content.strip(),
                    "pattern": f.pattern,
                }
                for f in self.findings
            ],
        }


class HotspotScanner:
    """Scanner for quality hotspots."""

    # Source directories to scan
    SOURCE_DIRS: ClassVar[list[Path]] = [
        PROJECT_ROOT / "src" / "ace_lite",
    ]

    # Test directories to scan
    TEST_DIRS: ClassVar[list[Path]] = [
        PROJECT_ROOT / "tests" / "unit",
        PROJECT_ROOT / "tests" / "integration",
    ]

    # Exclude patterns
    EXCLUDE_PATTERNS: ClassVar[list[str]] = [
        "__pycache__",
        ".pyc",
        ".pyo",
        "test_fixtures",
        "fixtures",
    ]

    # Scan patterns for each metric
    SCAN_PATTERNS: ClassVar[dict[str, dict[str, Any]]] = {
        "M-ARCH-01": {
            "name": "dict_fallback_sites",
            "description": "裸 dict/ctx.state/.get() 防御代码位置",
            "patterns": [
                # Bare dict with Any
                (r"dict\s*\<\s*str\s*,\s*Any\s*\>", "bare_dict_any"),
                # ctx.state access
                (r"ctx\.state\s*\[", "ctx_state_access"),
                # ctx.state.get()
                (r"ctx\.state\.get\(", "ctx_state_get"),
                # .get() chains
                (r'\.get\(\s*["\'][^"\']+["\']\s*\)\s*\.get\(', "nested_get_chain"),
            ],
            "exclude_files": [],
        },
        "M-CACHE-01": {
            "name": "cache_deepcopy_count",
            "description": "copy.deepcopy 调用次数",
            "patterns": [
                (r"copy\.deepcopy\(", "deepcopy_call"),
                (r"from\s+copy\s+import\s+deepcopy", "deepcopy_import"),
            ],
            "include_files": [
                "cache",
                "repomap",
            ],
        },
        "M-REL-01": {
            "name": "broad_exception_sites",
            "description": "宽泛 except Exception 站点",
            "patterns": [
                # except Exception:
                (r"except\s+Exception\s*:", "broad_exception"),
                # except Exception as e:
                (r"except\s+Exception\s+as\s+\w+\s*:", "broad_exception_named"),
                # except:
                (r"except\s*:\s*(?:  # noqa)", "bare_except"),
            ],
            "exclude_patterns": [
                r"except\s+\(.*Exception.*\)",  # Tupled exceptions are OK
                r"except\s+.*Error\s*:",  # Specific errors are OK
            ],
        },
        "M-PLAN-01": {
            "name": "plan_quick_rule_cluster_count",
            "description": "marker/boost/domain 规则聚类",
            "patterns": [
                # Marker definitions
                (r"_MARKER[S]?\s*=\s*\[", "marker_definition"),
                # Boost/Penalty patterns
                (r"_?(boost|penalty)\w*\s*[=:]", "boost_penalty"),
                # Domain patterns
                (r"_?(domain|path_match)\w*\s*[=:]", "domain_pattern"),
                # Intent patterns
                (r"_?(intent|strategy)\w*\s*[=:]", "intent_strategy"),
            ],
            "include_files": [
                "plan_quick",
            ],
        },
    }

    def __init__(self, root: Path | None = None):
        self.root = root or PROJECT_ROOT
        self.source_dirs = [
            self.root / "src" / "ace_lite",
        ]
        self.test_dirs = [
            self.root / "tests" / "unit",
            self.root / "tests" / "integration",
        ]

    def _should_scan_file(
        self, file_path: Path, include_files: list, exclude_patterns: list
    ) -> bool:
        """Check if file should be scanned."""
        # Check exclusions
        path_str = str(file_path)
        for pattern in self.EXCLUDE_PATTERNS:
            if pattern in path_str:
                return False

        # Check inclusions
        if include_files:
            return any(inc in path_str for inc in include_files)

        return True

    def _scan_file(self, file_path: Path, patterns: list) -> list[HotspotResult]:
        """Scan a single file for hotspot patterns."""
        results = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            return results

        lines = content.splitlines()
        for line_no, line in enumerate(lines, start=1):
            for pattern, pattern_name in patterns:
                if re.search(pattern, line):
                    results.append(
                        HotspotResult(
                            metric_id="",
                            file_path=str(file_path.relative_to(self.root)),
                            line_number=line_no,
                            line_content=line,
                            pattern=pattern_name,
                        )
                    )
        return results

    def _should_exclude_line(self, line: str, exclude_patterns: list) -> bool:
        """Check if line should be excluded based on exclusion patterns."""
        return any(re.search(pattern, line) for pattern in exclude_patterns)

    def scan_metric(self, metric_id: str, include_tests: bool = False) -> ScanResults:
        """Scan for a specific metric."""
        config = self.SCAN_PATTERNS.get(metric_id)
        if not config:
            return ScanResults(
                metric_id=metric_id,
                metric_name="unknown",
                total_count=0,
            )

        all_dirs = list(self.source_dirs)
        if include_tests:
            all_dirs.extend(self.test_dirs)

        include_files = config.get("include_files", [])
        exclude_patterns = config.get("exclude_patterns", [])

        findings = []
        for scan_dir in all_dirs:
            if not scan_dir.exists():
                continue

            for file_path in scan_dir.rglob("*.py"):
                if not self._should_scan_file(file_path, include_files, []):
                    continue

                for pattern, pattern_name in config["patterns"]:
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                    except (OSError, UnicodeDecodeError):
                        continue

                    for line_no, line in enumerate(content.splitlines(), start=1):
                        # Skip excluded patterns
                        if exclude_patterns and self._should_exclude_line(line, exclude_patterns):
                            continue

                        if re.search(pattern, line):
                            findings.append(
                                HotspotResult(
                                    metric_id=metric_id,
                                    file_path=str(file_path.relative_to(self.root)),
                                    line_number=line_no,
                                    line_content=line,
                                    pattern=pattern_name,
                                )
                            )

        return ScanResults(
            metric_id=metric_id,
            metric_name=config["name"],
            total_count=len(findings),
            findings=findings,
        )

    def scan_all(self, metric_ids: list[str] | None = None, include_tests: bool = True) -> dict:
        """Scan for all or specific metrics."""
        if metric_ids is None:
            metric_ids = list(self.SCAN_PATTERNS.keys())

        results = {}
        for metric_id in metric_ids:
            scan_result = self.scan_metric(metric_id, include_tests=include_tests)
            results[metric_id] = scan_result.to_dict()

        return results


def build_hotspots_report(scanner: HotspotScanner, metric_ids: list[str] | None = None) -> dict:
    """Build the complete hotspots report."""
    results = scanner.scan_all(metric_ids=metric_ids)

    # Calculate summary
    summary = {}
    for metric_id, data in results.items():
        summary[metric_id] = {
            "metric_name": data["metric_name"],
            "total_count": data["total_count"],
        }

    return {
        "schema_version": "static_hotspots_v1",
        "prd": "91_QUALITY_OPTIMIZATION_PRD_2026-04-12",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(scanner.root),
        "scan_summary": summary,
        "detailed_results": results,
    }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Static Hotspot Scanner for Quality Optimization (PRD-91)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output JSON file path (default: print to stdout)",
    )
    parser.add_argument(
        "--filter",
        "-f",
        action="append",
        dest="filters",
        help="Filter by metric ID (can be specified multiple times)",
    )
    parser.add_argument(
        "--no-tests",
        action="store_true",
        help="Exclude test files from scan",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Only print summary, not detailed findings",
    )

    args = parser.parse_args()

    scanner = HotspotScanner()

    metric_ids = args.filters if args.filters else None
    report = build_hotspots_report(scanner, metric_ids=metric_ids)

    if args.summary:
        print("Hotspot Scan Summary:")
        print("-" * 50)
        for metric_id, data in report["scan_summary"].items():
            print(f"  {metric_id}: {data['metric_name']} = {data['total_count']}")
        return 0

    json_output = json.dumps(report, indent=2, ensure_ascii=False)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json_output, encoding="utf-8")
        print(f"Hotspots report written to: {args.output}")
        return 0
    else:
        print(json_output)
        return 0


if __name__ == "__main__":
    sys.exit(main())
