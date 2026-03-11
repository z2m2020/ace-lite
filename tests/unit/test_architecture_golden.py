"""Golden tests for architecture refactor safety nets.

These tests capture baseline behavior that must remain invariant across
the architecture refactoring phases defined in ARCHITECTURE_EXECUTION_PLAN_V2.md.

Phase 0 deliverable: freeze current behavior before major refactor.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest

from ace_lite.orchestrator import (
    BM25_B,
    BM25_K1,
    CHUNK_FILE_PRIOR_WEIGHT,
    CHUNK_PATH_MATCH,
    CHUNK_SYMBOL_EXACT,
    HEUR_PATH_EXACT,
    HEUR_SYMBOL_EXACT,
    HYBRID_BM25_WEIGHT,
    HYBRID_HEURISTIC_WEIGHT,
    HYBRID_RRF_K_DEFAULT,
    AceOrchestrator,
)
from ace_lite.orchestrator_config import OrchestratorConfig


def _build_orchestrator(**kwargs: Any) -> AceOrchestrator:
    memory_provider = kwargs.pop("memory_provider", None)

    config_payload: dict[str, Any] = {}

    skill_manifest = kwargs.pop("skill_manifest", None)
    if skill_manifest is not None:
        config_payload["skills"] = {"manifest": skill_manifest}

    index_languages = kwargs.pop("index_languages", None)
    index_cache_path = kwargs.pop("index_cache_path", None)
    if index_languages is not None or index_cache_path is not None:
        config_payload["index"] = {}
        if index_languages is not None:
            config_payload["index"]["languages"] = index_languages
        if index_cache_path is not None:
            config_payload["index"]["cache_path"] = index_cache_path

    candidate_ranker = kwargs.pop("candidate_ranker", None)
    if candidate_ranker is not None:
        config_payload.setdefault("retrieval", {})["candidate_ranker"] = candidate_ranker

    repomap_enabled = kwargs.pop("repomap_enabled", None)
    if repomap_enabled is not None:
        config_payload["repomap"] = {"enabled": bool(repomap_enabled)}

    lsp_enabled = kwargs.pop("lsp_enabled", None)
    if lsp_enabled is not None:
        config_payload["lsp"] = {"enabled": bool(lsp_enabled)}

    cochange_enabled = kwargs.pop("cochange_enabled", None)
    if cochange_enabled is not None:
        config_payload["cochange"] = {"enabled": bool(cochange_enabled)}

    plugins_enabled = kwargs.pop("plugins_enabled", None)
    if plugins_enabled is not None:
        config_payload["plugins"] = {"enabled": bool(plugins_enabled)}

    if kwargs:
        unexpected = ", ".join(sorted(str(key) for key in kwargs))
        raise ValueError(f"Unexpected orchestrator kwargs: {unexpected}")

    return AceOrchestrator(
        memory_provider=memory_provider,
        config=OrchestratorConfig(**config_payload),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a minimal sample repository for testing."""
    root = tmp_path
    (root / "src" / "app").mkdir(parents=True, exist_ok=True)

    (root / "src" / "app" / "core.py").write_text(
        textwrap.dedent(
            """
            def process_data(input: str) -> str:
                return input.upper()

            class DataProcessor:
                def __init__(self, config: dict):
                    self.config = config

                def run(self, data: str) -> str:
                    return self.process(data)

                def process(self, data: str) -> str:
                    return data.strip()
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    (root / "src" / "app" / "utils.py").write_text(
        textwrap.dedent(
            """
            from .core import process_data

            def format_output(data: str) -> str:
                return f"Result: {process_data(data)}"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    return root


@pytest.fixture
def fake_skill_manifest() -> list[dict[str, Any]]:
    return [
        {
            "name": "test-skill",
            "path": "skills/test-skill.md",
            "description": "A test skill",
            "priority": 1,
            "match_keywords": ["fix", "bug"],
        }
    ]


# ---------------------------------------------------------------------------
# Phase 0.1: Pipeline Order Invariance
# ---------------------------------------------------------------------------


class TestPipelineOrderInvariance:
    """Ensure PIPELINE_ORDER remains stable across refactors."""

    EXPECTED_ORDER = ("memory", "index", "repomap", "augment", "skills", "source_plan")

    def test_pipeline_order_constant_matches_expected(self) -> None:
        """PIPELINE_ORDER must match the documented order."""
        assert AceOrchestrator.PIPELINE_ORDER == self.EXPECTED_ORDER

    def test_pipeline_order_length_is_six(self) -> None:
        """Pipeline must have exactly 6 stages."""
        assert len(AceOrchestrator.PIPELINE_ORDER) == 6

    def test_pipeline_order_tuple_is_immutable(self) -> None:
        """PIPELINE_ORDER must be a tuple (immutable)."""
        assert isinstance(AceOrchestrator.PIPELINE_ORDER, tuple)

    def test_plan_output_matches_pipeline_order(
        self, sample_repo: Path, fake_skill_manifest: list[dict[str, Any]]
    ) -> None:
        """plan() output must respect PIPELINE_ORDER in stage_metrics."""
        orchestrator = _build_orchestrator(
            skill_manifest=fake_skill_manifest,
            index_languages=["python"],
            index_cache_path=sample_repo / "context-map" / "index.json",
            repomap_enabled=False,
            lsp_enabled=False,
            cochange_enabled=False,
            plugins_enabled=False,
        )

        payload = orchestrator.plan(
            query="fix bug in process_data",
            repo="test-repo",
            root=str(sample_repo),
        )

        # Stage metrics must follow pipeline order
        stage_names = [
            metric["stage"] for metric in payload["observability"]["stage_metrics"]
        ]
        assert tuple(stage_names) == self.EXPECTED_ORDER

        # Pipeline order in output must match constant
        assert tuple(payload["pipeline_order"]) == self.EXPECTED_ORDER


# ---------------------------------------------------------------------------
# Phase 0.2: Key Source Plan Fields
# ---------------------------------------------------------------------------


class TestSourcePlanFields:
    """Ensure source_plan stage emits required fields."""

    REQUIRED_FIELDS = frozenset({
        "steps",
        "constraints",
        "candidate_chunks",
        "validation_tests",
    })

    def test_source_plan_has_required_fields(
        self, sample_repo: Path, fake_skill_manifest: list[dict[str, Any]]
    ) -> None:
        """source_plan must contain all required top-level fields."""
        orchestrator = _build_orchestrator(
            skill_manifest=fake_skill_manifest,
            index_languages=["python"],
            index_cache_path=sample_repo / "context-map" / "index.json",
            repomap_enabled=False,
            lsp_enabled=False,
            cochange_enabled=False,
            plugins_enabled=False,
        )

        payload = orchestrator.plan(
            query="fix bug in process_data",
            repo="test-repo",
            root=str(sample_repo),
        )

        source_plan = payload.get("source_plan", {})
        missing = self.REQUIRED_FIELDS - set(source_plan.keys())
        assert not missing, f"Missing required fields: {missing}"

    def test_source_plan_steps_is_list(
        self, sample_repo: Path, fake_skill_manifest: list[dict[str, Any]]
    ) -> None:
        """steps must be a list."""
        orchestrator = _build_orchestrator(
            skill_manifest=fake_skill_manifest,
            index_languages=["python"],
            index_cache_path=sample_repo / "context-map" / "index.json",
            repomap_enabled=False,
            lsp_enabled=False,
            cochange_enabled=False,
            plugins_enabled=False,
        )

        payload = orchestrator.plan(
            query="fix bug in process_data",
            repo="test-repo",
            root=str(sample_repo),
        )

        assert isinstance(payload["source_plan"]["steps"], list)

    def test_source_plan_candidate_chunks_is_list(
        self, sample_repo: Path, fake_skill_manifest: list[dict[str, Any]]
    ) -> None:
        """candidate_chunks must be a list."""
        orchestrator = _build_orchestrator(
            skill_manifest=fake_skill_manifest,
            index_languages=["python"],
            index_cache_path=sample_repo / "context-map" / "index.json",
            repomap_enabled=False,
            lsp_enabled=False,
            cochange_enabled=False,
            plugins_enabled=False,
        )

        payload = orchestrator.plan(
            query="fix bug in process_data",
            repo="test-repo",
            root=str(sample_repo),
        )

        assert isinstance(payload["source_plan"]["candidate_chunks"], list)


# ---------------------------------------------------------------------------
# Phase 0.3: Candidate Ranker Selection Behavior
# ---------------------------------------------------------------------------


class TestCandidateRankerSelection:
    """Ensure ranker selection logic remains deterministic."""

    RANKER_CHOICES = ("heuristic", "bm25_lite", "hybrid_re2", "rrf_hybrid")

    def test_valid_ranker_choices_constant(self) -> None:
        """CANDIDATE_RANKERS must match documented choices."""
        assert AceOrchestrator.CANDIDATE_RANKERS == self.RANKER_CHOICES

    def test_invalid_ranker_falls_back_to_heuristic(self) -> None:
        """Invalid ranker must fall back to heuristic (normalized behavior)."""
        orchestrator = _build_orchestrator(
            candidate_ranker="invalid_ranker",
            repomap_enabled=False,
            lsp_enabled=False,
            cochange_enabled=False,
            plugins_enabled=False,
        )
        assert orchestrator.config.retrieval.candidate_ranker == "heuristic"

    def test_heuristic_ranker_produces_deterministic_output(
        self, sample_repo: Path, fake_skill_manifest: list[dict[str, Any]]
    ) -> None:
        """heuristic ranker must produce stable output for same input."""
        orchestrator = _build_orchestrator(
            skill_manifest=fake_skill_manifest,
            index_languages=["python"],
            index_cache_path=sample_repo / "context-map" / "index.json",
            candidate_ranker="heuristic",
            repomap_enabled=False,
            lsp_enabled=False,
            cochange_enabled=False,
            plugins_enabled=False,
        )

        payload1 = orchestrator.plan(
            query="fix bug in process_data",
            repo="test-repo",
            root=str(sample_repo),
        )

        payload2 = orchestrator.plan(
            query="fix bug in process_data",
            repo="test-repo",
            root=str(sample_repo),
        )

        # Candidate paths must be identical
        paths1 = [c["path"] for c in payload1["index"]["candidate_files"]]
        paths2 = [c["path"] for c in payload2["index"]["candidate_files"]]
        assert paths1 == paths2


# ---------------------------------------------------------------------------
# Phase 0.4: Scoring Constants Baseline
# ---------------------------------------------------------------------------


class TestScoringConstantsBaseline:
    """Capture scoring constant values for refactor safety.

    These values must be preserved when extracted to scoring_config.py.
    Any change indicates potential behavior drift.
    """

    # Chunk scoring constants
    EXPECTED_CHUNK_FILE_PRIOR_WEIGHT = 0.35
    EXPECTED_CHUNK_PATH_MATCH = 1.0
    EXPECTED_CHUNK_SYMBOL_EXACT = 2.5

    # Heuristic ranker constants
    EXPECTED_HEUR_PATH_EXACT = 3.0
    EXPECTED_HEUR_SYMBOL_EXACT = 3.0

    # BM25 constants
    EXPECTED_BM25_K1 = 1.2
    EXPECTED_BM25_B = 0.75

    # Hybrid ranker constants
    EXPECTED_HYBRID_BM25_WEIGHT = 0.45
    EXPECTED_HYBRID_HEURISTIC_WEIGHT = 0.45
    EXPECTED_HYBRID_RRF_K_DEFAULT = 60

    def test_chunk_file_prior_weight(self) -> None:
        assert CHUNK_FILE_PRIOR_WEIGHT == self.EXPECTED_CHUNK_FILE_PRIOR_WEIGHT

    def test_chunk_path_match(self) -> None:
        assert CHUNK_PATH_MATCH == self.EXPECTED_CHUNK_PATH_MATCH

    def test_chunk_symbol_exact(self) -> None:
        assert CHUNK_SYMBOL_EXACT == self.EXPECTED_CHUNK_SYMBOL_EXACT

    def test_heur_path_exact(self) -> None:
        assert HEUR_PATH_EXACT == self.EXPECTED_HEUR_PATH_EXACT

    def test_heur_symbol_exact(self) -> None:
        assert HEUR_SYMBOL_EXACT == self.EXPECTED_HEUR_SYMBOL_EXACT

    def test_bm25_k1(self) -> None:
        assert BM25_K1 == self.EXPECTED_BM25_K1

    def test_bm25_b(self) -> None:
        assert BM25_B == self.EXPECTED_BM25_B

    def test_hybrid_bm25_weight(self) -> None:
        assert HYBRID_BM25_WEIGHT == self.EXPECTED_HYBRID_BM25_WEIGHT

    def test_hybrid_heuristic_weight(self) -> None:
        assert HYBRID_HEURISTIC_WEIGHT == self.EXPECTED_HYBRID_HEURISTIC_WEIGHT

    def test_hybrid_rrf_k_default(self) -> None:
        assert HYBRID_RRF_K_DEFAULT == self.EXPECTED_HYBRID_RRF_K_DEFAULT


# ---------------------------------------------------------------------------
# Phase 0.5: Output Schema Stability
# ---------------------------------------------------------------------------


class TestOutputSchemaStability:
    """Ensure top-level output schema remains stable."""

    REQUIRED_TOP_LEVEL_FIELDS = frozenset({
        "schema_version",
        "query",
        "repo",
        "root",
        "pipeline_order",
        "conventions",
        "memory",
        "index",
        "repomap",
        "augment",
        "skills",
        "source_plan",
        "observability",
    })

    def test_required_top_level_fields_present(
        self, sample_repo: Path, fake_skill_manifest: list[dict[str, Any]]
    ) -> None:
        """All required top-level fields must be present in plan output."""
        orchestrator = _build_orchestrator(
            skill_manifest=fake_skill_manifest,
            index_languages=["python"],
            index_cache_path=sample_repo / "context-map" / "index.json",
            repomap_enabled=False,
            lsp_enabled=False,
            cochange_enabled=False,
            plugins_enabled=False,
        )

        payload = orchestrator.plan(
            query="fix bug",
            repo="test-repo",
            root=str(sample_repo),
        )

        missing = self.REQUIRED_TOP_LEVEL_FIELDS - set(payload.keys())
        assert not missing, f"Missing top-level fields: {missing}"

    def test_observability_has_stage_metrics(
        self, sample_repo: Path, fake_skill_manifest: list[dict[str, Any]]
    ) -> None:
        """observability must contain stage_metrics."""
        orchestrator = _build_orchestrator(
            skill_manifest=fake_skill_manifest,
            index_languages=["python"],
            index_cache_path=sample_repo / "context-map" / "index.json",
            repomap_enabled=False,
            lsp_enabled=False,
            cochange_enabled=False,
            plugins_enabled=False,
        )

        payload = orchestrator.plan(
            query="fix bug",
            repo="test-repo",
            root=str(sample_repo),
        )

        assert "stage_metrics" in payload["observability"]
        assert isinstance(payload["observability"]["stage_metrics"], list)
