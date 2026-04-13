"""Performance Benchmark Framework for ACE-Lite

This module provides a framework for benchmarking performance-critical
operations to determine when to use experimental optimizations.

PRD-91 Phase 3: Experimental Performance Optimization

The following features are experimental and require benchmark validation:
- ProcessPoolExecutor for parallel parsing
- orjson for JSON serialization

The benchmark framework helps determine:
1. Baseline performance with standard library
2. Performance with experimental optimizations
3. Whether optimizations provide positive gains
4. Optimal configuration for the current environment
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

# =============================================================================
# Benchmark Results
# =============================================================================


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""

    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    std_dev_ms: float | None = None
    memory_delta_bytes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ops_per_second(self) -> float:
        """Calculate operations per second."""
        if self.total_time_ms > 0:
            return (self.iterations / self.total_time_ms) * 1000
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time_ms": self.total_time_ms,
            "avg_time_ms": self.avg_time_ms,
            "min_time_ms": self.min_time_ms,
            "max_time_ms": self.max_time_ms,
            "std_dev_ms": self.std_dev_ms,
            "ops_per_second": self.ops_per_second,
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkComparison:
    """Comparison between two benchmark results."""

    baseline: BenchmarkResult
    optimized: BenchmarkResult

    @property
    def speedup_ratio(self) -> float:
        """Calculate speedup ratio (baseline / optimized)."""
        if self.optimized.avg_time_ms > 0:
            return self.baseline.avg_time_ms / self.optimized.avg_time_ms
        return 1.0

    @property
    def time_saved_ms(self) -> float:
        """Calculate time saved per operation in ms."""
        return self.baseline.avg_time_ms - self.optimized.avg_time_ms

    @property
    def percent_improvement(self) -> float:
        """Calculate percentage improvement."""
        if self.baseline.avg_time_ms > 0:
            return (
                (self.baseline.avg_time_ms - self.optimized.avg_time_ms)
                / self.baseline.avg_time_ms
            ) * 100
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "baseline": self.baseline.to_dict(),
            "optimized": self.optimized.to_dict(),
            "speedup_ratio": self.speedup_ratio,
            "time_saved_ms": self.time_saved_ms,
            "percent_improvement": self.percent_improvement,
        }


# =============================================================================
# Benchmark Runner
# =============================================================================


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runner."""

    # Number of warmup iterations
    warmup_iterations: int = 3

    # Number of actual benchmark iterations
    iterations: int = 10

    # Minimum time in seconds to run each benchmark
    min_duration_seconds: float = 0.1

    # Enable memory tracking
    track_memory: bool = False

    # Confidence threshold for accepting results
    confidence_threshold: float = 0.95


class BenchmarkRunner:
    """Runner for performance benchmarks."""

    def __init__(self, config: BenchmarkConfig | None = None):
        """Initialize the benchmark runner.

        Args:
            config: Optional benchmark configuration
        """
        self.config = config or BenchmarkConfig()

    def run(
        self,
        name: str,
        func: Callable[[], Any],
        *,
        warmup: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> BenchmarkResult:
        """Run a single benchmark.

        Args:
            name: Name of the benchmark
            func: Function to benchmark
            warmup: Whether to run warmup iterations
            metadata: Additional metadata for the result

        Returns:
            Benchmark result
        """
        import statistics

        if warmup:
            # Warmup iterations
            for _ in range(self.config.warmup_iterations):
                func()

        # Benchmark iterations
        times_ms: list[float] = []
        start_time = time.perf_counter()

        for _ in range(self.config.iterations):
            iter_start = time.perf_counter()
            func()
            iter_end = time.perf_counter()
            times_ms.append((iter_end - iter_start) * 1000)

        total_time_ms = (time.perf_counter() - start_time) * 1000

        # Calculate statistics
        avg_time_ms = sum(times_ms) / len(times_ms)
        min_time_ms = min(times_ms)
        max_time_ms = max(times_ms)
        std_dev_ms = statistics.stdev(times_ms) if len(times_ms) > 1 else None

        return BenchmarkResult(
            name=name,
            iterations=self.config.iterations,
            total_time_ms=total_time_ms,
            avg_time_ms=avg_time_ms,
            min_time_ms=min_time_ms,
            max_time_ms=max_time_ms,
            std_dev_ms=std_dev_ms,
            metadata=metadata or {},
        )

    def compare(
        self,
        name: str,
        baseline_func: Callable[[], Any],
        optimized_func: Callable[[], Any],
    ) -> BenchmarkComparison:
        """Compare baseline and optimized implementations.

        Args:
            name: Name of the benchmark
            baseline_func: Baseline implementation
            optimized_func: Optimized implementation

        Returns:
            Comparison result
        """
        baseline_result = self.run(f"{name}_baseline", baseline_func)
        optimized_result = self.run(f"{name}_optimized", optimized_func)

        return BenchmarkComparison(
            baseline=baseline_result,
            optimized=optimized_result,
        )


# =============================================================================
# Memory Tracking
# =============================================================================


@contextmanager
def track_memory():
    """Context manager to track memory usage.

    Yields:
        Dict with memory tracking functions
    """
    import gc

    try:
        import psutil
    except ImportError:
        psutil = None

    class MemoryTracker:
        def __init__(self):
            self.start_rss = 0
            self.start_vms = 0

        def snapshot(self) -> dict[str, int]:
            """Get current memory snapshot."""
            gc.collect()
            if psutil:
                process = psutil.Process()
                return {
                    "rss": process.memory_info().rss,
                    "vms": process.memory_info().vms,
                }
            return {}

        def start(self) -> None:
            """Start tracking."""
            snapshot = self.snapshot()
            self.start_rss = snapshot.get("rss", 0)
            self.start_vms = snapshot.get("vms", 0)

        def delta(self) -> dict[str, int]:
            """Get memory delta since start."""
            snapshot = self.snapshot()
            return {
                "rss_delta": snapshot.get("rss", 0) - self.start_rss,
                "vms_delta": snapshot.get("vms", 0) - self.start_vms,
            }

    tracker = MemoryTracker()
    tracker.start()
    yield tracker
    # Memory tracked through delta() method


# =============================================================================
# Pre-built Benchmarks
# =============================================================================


def benchmark_json_serialization(
    data: dict[str, Any],
    iterations: int = 1000,
) -> dict[str, BenchmarkResult]:
    """Benchmark JSON serialization performance.

    Args:
        data: Data to serialize
        iterations: Number of iterations

    Returns:
        Dict of benchmark results keyed by implementation
    """
    results: dict[str, BenchmarkResult] = {}
    runner = BenchmarkRunner(BenchmarkConfig(iterations=iterations))

    # Standard json
    def standard_serialize():
        return json.dumps(data)

    def standard_parse():
        return json.loads(json.dumps(data))

    results["json_dumps"] = runner.run("json_dumps", standard_serialize)
    results["json_loads"] = runner.run("json_loads", standard_parse)

    # orjson if available
    try:
        import orjson

        def orjson_serialize():
            return orjson.dumps(data)

        def orjson_parse():
            return orjson.loads(orjson.dumps(data))

        results["orjson_dumps"] = runner.run("orjson_dumps", orjson_serialize)
        results["orjson_loads"] = runner.run("orjson_loads", orjson_parse)
    except ImportError:
        pass

    return results


def benchmark_parallel_processing(
    tasks: list[Callable[[], Any]],
    iterations: int = 10,
) -> dict[str, BenchmarkResult]:
    """Benchmark parallel processing performance.

    Args:
        tasks: List of tasks to process
        iterations: Number of iterations

    Returns:
        Dict of benchmark results keyed by implementation
    """
    results: dict[str, BenchmarkResult] = {}
    runner = BenchmarkRunner(BenchmarkConfig(iterations=iterations))

    # Sequential processing
    def sequential():
        for task in tasks:
            task()

    results["sequential"] = runner.run("sequential", sequential)

    # ThreadPoolExecutor if available
    try:
        from concurrent.futures import ThreadPoolExecutor

        def threadpool():
            with ThreadPoolExecutor() as executor:
                list(executor.map(lambda t: t(), tasks))

        results["threadpool"] = runner.run("threadpool", threadpool)
    except ImportError:
        pass

    # ProcessPoolExecutor if available
    try:
        from concurrent.futures import ProcessPoolExecutor

        def processpool():
            with ProcessPoolExecutor() as executor:
                list(executor.map(lambda t: t(), tasks))

        results["processpool"] = runner.run("processpool", processpool)
    except ImportError:
        pass

    return results


# =============================================================================
# Auto-tuning
# =============================================================================


@dataclass
class TuningRecommendation:
    """Recommendation for enabling/disabling an optimization."""

    feature: str
    recommended: bool
    confidence: float
    speedup_ratio: float
    reasoning: str


def determine_optimization(
    feature: str,
    baseline_func: Callable[[], Any],
    optimized_func: Callable[[], Any],
    threshold: float = 1.1,
) -> TuningRecommendation:
    """Determine whether to recommend an optimization.

    Args:
        feature: Name of the feature
        baseline_func: Baseline implementation
        optimized_func: Optimized implementation
        threshold: Minimum speedup ratio to recommend

    Returns:
        Tuning recommendation
    """
    runner = BenchmarkRunner()
    comparison = runner.compare(feature, baseline_func, optimized_func)

    speedup = comparison.speedup_ratio
    recommended = speedup >= threshold
    confidence = min(speedup / threshold, 1.0) if recommended else 0.5

    reasoning_parts = [
        f"Speedup: {speedup:.2f}x",
        f"Time saved: {comparison.time_saved_ms:.2f}ms per operation",
    ]
    if recommended:
        reasoning_parts.append(f"Exceeds threshold of {threshold}x")
    else:
        reasoning_parts.append(f"Below threshold of {threshold}x")

    return TuningRecommendation(
        feature=feature,
        recommended=recommended,
        confidence=confidence,
        speedup_ratio=speedup,
        reasoning="; ".join(reasoning_parts),
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "BenchmarkComparison",
    "BenchmarkConfig",
    "BenchmarkResult",
    "BenchmarkRunner",
    "TuningRecommendation",
    "benchmark_json_serialization",
    "benchmark_parallel_processing",
    "determine_optimization",
    "track_memory",
]
