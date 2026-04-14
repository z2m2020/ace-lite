"""Unit tests for performance_benchmark module.

Tests verify the performance benchmark framework (QO-3101/QO-3102).
"""

from __future__ import annotations

import time

from ace_lite.performance_benchmark import (
    BenchmarkComparison,
    BenchmarkConfig,
    BenchmarkGateThresholds,
    BenchmarkResult,
    BenchmarkRunner,
    TuningRecommendation,
    benchmark_json_serialization,
    determine_optimization,
    evaluate_benchmark_gate,
)


class TestBenchmarkResult:
    """Tests for BenchmarkResult."""

    def test_creation(self):
        """Test basic creation."""
        result = BenchmarkResult(
            name="test",
            iterations=10,
            total_time_ms=100.0,
            avg_time_ms=10.0,
            min_time_ms=8.0,
            max_time_ms=12.0,
        )

        assert result.name == "test"
        assert result.iterations == 10
        assert result.total_time_ms == 100.0
        assert result.avg_time_ms == 10.0

    def test_ops_per_second(self):
        """Test ops per second calculation."""
        result = BenchmarkResult(
            name="test",
            iterations=100,
            total_time_ms=1000.0,  # 1 second
            avg_time_ms=10.0,
            min_time_ms=8.0,
            max_time_ms=12.0,
        )

        assert result.ops_per_second == 100.0

    def test_ops_per_second_zero_time(self):
        """Test ops per second with zero time."""
        result = BenchmarkResult(
            name="test",
            iterations=100,
            total_time_ms=0.0,
            avg_time_ms=0.0,
            min_time_ms=0.0,
            max_time_ms=0.0,
        )

        assert result.ops_per_second == 0.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = BenchmarkResult(
            name="test",
            iterations=10,
            total_time_ms=100.0,
            avg_time_ms=10.0,
            min_time_ms=8.0,
            max_time_ms=12.0,
            memory_delta_bytes=256,
        )

        d = result.to_dict()
        assert d["name"] == "test"
        assert d["iterations"] == 10
        assert d["memory_delta_bytes"] == 256
        assert d["ops_per_second"] > 0


class TestBenchmarkComparison:
    """Tests for BenchmarkComparison."""

    def test_creation(self):
        """Test basic creation."""
        baseline = BenchmarkResult(
            name="baseline",
            iterations=10,
            total_time_ms=100.0,
            avg_time_ms=10.0,
            min_time_ms=8.0,
            max_time_ms=12.0,
        )
        optimized = BenchmarkResult(
            name="optimized",
            iterations=10,
            total_time_ms=50.0,
            avg_time_ms=5.0,
            min_time_ms=4.0,
            max_time_ms=6.0,
        )

        comparison = BenchmarkComparison(baseline=baseline, optimized=optimized)

        assert comparison.baseline is baseline
        assert comparison.optimized is optimized

    def test_speedup_ratio(self):
        """Test speedup ratio calculation."""
        baseline = BenchmarkResult(
            name="baseline",
            iterations=10,
            total_time_ms=100.0,
            avg_time_ms=10.0,
            min_time_ms=8.0,
            max_time_ms=12.0,
        )
        optimized = BenchmarkResult(
            name="optimized",
            iterations=10,
            total_time_ms=50.0,
            avg_time_ms=5.0,
            min_time_ms=4.0,
            max_time_ms=6.0,
        )

        comparison = BenchmarkComparison(baseline=baseline, optimized=optimized)

        assert comparison.speedup_ratio == 2.0  # 10.0 / 5.0

    def test_time_saved(self):
        """Test time saved calculation."""
        baseline = BenchmarkResult(
            name="baseline",
            iterations=10,
            total_time_ms=100.0,
            avg_time_ms=10.0,
            min_time_ms=8.0,
            max_time_ms=12.0,
        )
        optimized = BenchmarkResult(
            name="optimized",
            iterations=10,
            total_time_ms=60.0,
            avg_time_ms=6.0,
            min_time_ms=5.0,
            max_time_ms=7.0,
        )

        comparison = BenchmarkComparison(baseline=baseline, optimized=optimized)

        assert comparison.time_saved_ms == 4.0  # 10.0 - 6.0

    def test_percent_improvement(self):
        """Test percentage improvement calculation."""
        baseline = BenchmarkResult(
            name="baseline",
            iterations=10,
            total_time_ms=100.0,
            avg_time_ms=10.0,
            min_time_ms=8.0,
            max_time_ms=12.0,
        )
        optimized = BenchmarkResult(
            name="optimized",
            iterations=10,
            total_time_ms=50.0,
            avg_time_ms=5.0,
            min_time_ms=4.0,
            max_time_ms=6.0,
        )

        comparison = BenchmarkComparison(baseline=baseline, optimized=optimized)

        assert comparison.percent_improvement == 50.0  # (10-5)/10 * 100

    def test_memory_saved_bytes(self):
        """Test resident-memory savings calculation."""
        baseline = BenchmarkResult(
            name="baseline",
            iterations=10,
            total_time_ms=100.0,
            avg_time_ms=10.0,
            min_time_ms=8.0,
            max_time_ms=12.0,
            memory_delta_bytes=8192,
        )
        optimized = BenchmarkResult(
            name="optimized",
            iterations=10,
            total_time_ms=50.0,
            avg_time_ms=5.0,
            min_time_ms=4.0,
            max_time_ms=6.0,
            memory_delta_bytes=4096,
        )

        comparison = BenchmarkComparison(baseline=baseline, optimized=optimized)

        assert comparison.memory_saved_bytes == 4096
        assert comparison.memory_percent_improvement == 50.0

    def test_to_dict_includes_memory_comparison(self):
        """Test comparison serialization includes memory deltas when available."""
        baseline = BenchmarkResult(
            name="baseline",
            iterations=10,
            total_time_ms=100.0,
            avg_time_ms=10.0,
            min_time_ms=8.0,
            max_time_ms=12.0,
            memory_delta_bytes=2048,
        )
        optimized = BenchmarkResult(
            name="optimized",
            iterations=10,
            total_time_ms=50.0,
            avg_time_ms=5.0,
            min_time_ms=4.0,
            max_time_ms=6.0,
            memory_delta_bytes=1024,
        )

        comparison = BenchmarkComparison(baseline=baseline, optimized=optimized)

        payload = comparison.to_dict()

        assert payload["memory_saved_bytes"] == 1024
        assert payload["memory_percent_improvement"] == 50.0


class TestBenchmarkConfig:
    """Tests for BenchmarkConfig."""

    def test_defaults(self):
        """Test default configuration."""
        config = BenchmarkConfig()

        assert config.warmup_iterations == 3
        assert config.iterations == 10
        assert config.min_duration_seconds == 0.1
        assert config.track_memory is False
        assert config.confidence_threshold == 0.95

    def test_custom_config(self):
        """Test custom configuration."""
        config = BenchmarkConfig(
            warmup_iterations=5,
            iterations=20,
            track_memory=True,
        )

        assert config.warmup_iterations == 5
        assert config.iterations == 20
        assert config.track_memory is True


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner."""

    def test_run_simple(self):
        """Test running a simple benchmark."""
        runner = BenchmarkRunner(BenchmarkConfig(iterations=5))

        def simple_func():
            time.sleep(0.001)  # 1ms
            return 42

        result = runner.run("simple", simple_func)

        assert result.name == "simple"
        assert result.iterations == 5
        assert result.avg_time_ms > 0

    def test_run_with_warmup(self):
        """Test running benchmark with warmup."""
        runner = BenchmarkRunner(BenchmarkConfig(warmup_iterations=2, iterations=3))

        call_count = 0

        def counting_func():
            nonlocal call_count
            call_count += 1
            return call_count

        runner.run("counting", counting_func, warmup=True)

        # Should have 2 warmup + 3 actual = 5 calls
        assert call_count == 5

    def test_run_without_warmup(self):
        """Test running benchmark without warmup."""
        runner = BenchmarkRunner(BenchmarkConfig(iterations=3))

        call_count = 0

        def counting_func():
            nonlocal call_count
            call_count += 1
            return call_count

        runner.run("counting", counting_func, warmup=False)

        # Should have only 3 actual calls
        assert call_count == 3

    def test_compare(self):
        """Test comparing baseline and optimized."""
        runner = BenchmarkRunner(BenchmarkConfig(iterations=5))

        def baseline_func():
            time.sleep(0.002)
            return "baseline"

        def optimized_func():
            time.sleep(0.001)
            return "optimized"

        comparison = runner.compare("test", baseline_func, optimized_func)

        assert comparison.speedup_ratio > 1.0  # Optimized should be faster

    def test_run_with_memory_tracking(self, monkeypatch):
        """Test running benchmark with memory tracking enabled."""
        runner = BenchmarkRunner(BenchmarkConfig(iterations=3, track_memory=True))

        class _FakeTracker:
            def delta(self):
                return {"rss_delta": 4096, "vms_delta": 8192}

        class _FakeMemoryContext:
            def __enter__(self):
                return _FakeTracker()

            def __exit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(
            "ace_lite.performance_benchmark.track_memory",
            lambda: _FakeMemoryContext(),
        )

        result = runner.run("memory-tracked", lambda: 1)

        assert result.memory_delta_bytes == 4096


class TestDetermineOptimization:
    """Tests for determine_optimization."""

    def test_recommend_when_faster(self):
        """Test recommendation when optimized is faster."""
        def baseline():
            time.sleep(0.01)
            return 1

        def optimized():
            time.sleep(0.005)
            return 1

        recommendation = determine_optimization(
            "test_feature",
            baseline,
            optimized,
            threshold=1.5,
        )

        assert recommendation.feature == "test_feature"
        assert recommendation.recommended is True
        assert recommendation.speedup_ratio > 1.0

    def test_not_recommend_when_slower(self):
        """Test recommendation when optimized is slower."""
        def baseline():
            time.sleep(0.005)
            return 1

        def optimized():
            time.sleep(0.01)
            return 1

        recommendation = determine_optimization(
            "test_feature",
            baseline,
            optimized,
            threshold=1.1,
        )

        assert recommendation.recommended is False

    def test_reasoning_includes_memory_tradeoff_when_available(self, monkeypatch):
        """Test reasoning includes memory savings when comparison carries memory deltas."""

        def fake_compare(self, name, baseline_func, optimized_func):
            del self, name, baseline_func, optimized_func
            return BenchmarkComparison(
                baseline=BenchmarkResult(
                    name="baseline",
                    iterations=10,
                    total_time_ms=100.0,
                    avg_time_ms=10.0,
                    min_time_ms=8.0,
                    max_time_ms=12.0,
                    memory_delta_bytes=8192,
                ),
                optimized=BenchmarkResult(
                    name="optimized",
                    iterations=10,
                    total_time_ms=50.0,
                    avg_time_ms=5.0,
                    min_time_ms=4.0,
                    max_time_ms=6.0,
                    memory_delta_bytes=4096,
                ),
            )

        monkeypatch.setattr(BenchmarkRunner, "compare", fake_compare)

        recommendation = determine_optimization(
            "test_feature",
            lambda: 1,
            lambda: 1,
            threshold=1.1,
        )

        assert "Memory saved: 4096 bytes (50.00%)" in recommendation.reasoning


class TestEvaluateBenchmarkGate:
    """Tests for explicit benchmark regression gates."""

    def test_passes_when_all_thresholds_are_met(self):
        comparison = BenchmarkComparison(
            baseline=BenchmarkResult(
                name="baseline",
                iterations=10,
                total_time_ms=100.0,
                avg_time_ms=10.0,
                min_time_ms=8.0,
                max_time_ms=12.0,
                memory_delta_bytes=4096,
                metadata={"cache_hit_ratio": 0.20},
            ),
            optimized=BenchmarkResult(
                name="optimized",
                iterations=10,
                total_time_ms=50.0,
                avg_time_ms=5.0,
                min_time_ms=4.0,
                max_time_ms=6.0,
                memory_delta_bytes=1024,
                metadata={"cache_hit_ratio": 0.92},
            ),
        )

        gate = evaluate_benchmark_gate(
            name="json_codec",
            comparison=comparison,
            thresholds=BenchmarkGateThresholds(
                min_speedup_ratio=1.5,
                max_avg_time_ms=6.0,
                max_memory_delta_bytes=2048,
                min_cache_hit_ratio=0.8,
            ),
        )

        assert gate.passed is True
        assert gate.summary == "all benchmark gates passed"
        assert all(item["passed"] is True for item in gate.checks.values())

    def test_fails_when_required_cache_hit_ratio_is_missing(self):
        comparison = BenchmarkComparison(
            baseline=BenchmarkResult(
                name="baseline",
                iterations=10,
                total_time_ms=80.0,
                avg_time_ms=8.0,
                min_time_ms=7.0,
                max_time_ms=9.0,
            ),
            optimized=BenchmarkResult(
                name="optimized",
                iterations=10,
                total_time_ms=60.0,
                avg_time_ms=6.0,
                min_time_ms=5.0,
                max_time_ms=7.0,
            ),
        )

        gate = evaluate_benchmark_gate(
            name="index_cache",
            comparison=comparison,
            thresholds=BenchmarkGateThresholds(min_cache_hit_ratio=0.75),
        )

        assert gate.passed is False
        assert gate.checks["cache_hit_ratio"]["observed"] is None
        assert gate.summary == "benchmark gates failed: cache_hit_ratio"

    def test_passes_cold_and_warm_cache_gates_from_metadata(self):
        comparison = BenchmarkComparison(
            baseline=BenchmarkResult(
                name="baseline",
                iterations=10,
                total_time_ms=120.0,
                avg_time_ms=12.0,
                min_time_ms=10.0,
                max_time_ms=14.0,
            ),
            optimized=BenchmarkResult(
                name="optimized",
                iterations=10,
                total_time_ms=60.0,
                avg_time_ms=6.0,
                min_time_ms=5.0,
                max_time_ms=7.0,
                metadata={
                    "cold_avg_time_ms": 18.0,
                    "warm_avg_time_ms": 4.0,
                    "warm_cache_hit_ratio": 0.95,
                },
            ),
        )

        gate = evaluate_benchmark_gate(
            name="index_cache",
            comparison=comparison,
            thresholds=BenchmarkGateThresholds(
                max_cold_avg_time_ms=20.0,
                max_warm_avg_time_ms=5.0,
                min_warm_cache_hit_ratio=0.90,
            ),
        )

        assert gate.passed is True
        assert gate.checks["cold_avg_time_ms"]["passed"] is True
        assert gate.checks["warm_avg_time_ms"]["passed"] is True
        assert gate.checks["warm_cache_hit_ratio"]["passed"] is True

    def test_fails_when_cold_or_warm_metadata_gates_miss_thresholds(self):
        comparison = BenchmarkComparison(
            baseline=BenchmarkResult(
                name="baseline",
                iterations=10,
                total_time_ms=120.0,
                avg_time_ms=12.0,
                min_time_ms=10.0,
                max_time_ms=14.0,
            ),
            optimized=BenchmarkResult(
                name="optimized",
                iterations=10,
                total_time_ms=80.0,
                avg_time_ms=8.0,
                min_time_ms=7.0,
                max_time_ms=9.0,
                metadata={
                    "cold_avg_time_ms": 28.0,
                    "warm_avg_time_ms": 7.0,
                    "warm_cache_hit_ratio": 0.40,
                },
            ),
        )

        gate = evaluate_benchmark_gate(
            name="index_cache",
            comparison=comparison,
            thresholds=BenchmarkGateThresholds(
                max_cold_avg_time_ms=20.0,
                max_warm_avg_time_ms=5.0,
                min_warm_cache_hit_ratio=0.90,
            ),
        )

        assert gate.passed is False
        assert gate.summary == (
            "benchmark gates failed: cold_avg_time_ms, warm_avg_time_ms, warm_cache_hit_ratio"
        )


class TestBenchmarkJSONSerialization:
    """Tests for benchmark_json_serialization."""

    def test_benchmark_json(self):
        """Test benchmarking JSON serialization."""
        data = {"key": "value", "list": [1, 2, 3]}

        results = benchmark_json_serialization(data, iterations=10)

        assert "json_dumps" in results
        assert "json_loads" in results
        assert results["json_dumps"].avg_time_ms > 0


class TestBenchmarkParallelProcessing:
    """Tests for benchmark_parallel_processing."""

    def test_benchmark_sequential_only(self):
        """Test benchmarking sequential processing only.

        Note: ProcessPoolExecutor requires picklable functions,
        so we only test sequential processing here.
        """
        def task():
            time.sleep(0.001)
            return 42

        runner = BenchmarkRunner(BenchmarkConfig(iterations=3))

        def sequential():
            for _ in range(5):
                task()

        result = runner.run("sequential", sequential)

        assert result.name == "sequential"
        assert result.avg_time_ms > 0


class TestTuningRecommendation:
    """Tests for TuningRecommendation."""

    def test_creation(self):
        """Test basic creation."""
        recommendation = TuningRecommendation(
            feature="test",
            recommended=True,
            confidence=0.95,
            speedup_ratio=2.0,
            reasoning="Test reasoning",
        )

        assert recommendation.feature == "test"
        assert recommendation.recommended is True
        assert recommendation.confidence == 0.95
        assert recommendation.speedup_ratio == 2.0
