from __future__ import annotations

import json
from pathlib import Path

from ace_lite.chunking.scoring import score_chunk_candidate
from ace_lite.index_stage.scip_boost import apply_scip_boost
from ace_lite.rankers.bm25 import rank_candidates_bm25
from ace_lite.rankers.heuristic import rank_candidates_heuristic


def test_bm25_scoring_overlay_changes_candidate_scores() -> None:
    files_map = {
        "src/user_repo.py": {
            "language": "python",
            "module": "src.user_repo",
            "symbols": [
                {
                    "name": "getUserById",
                    "qualified_name": "src.user_repo.getUserById",
                }
            ],
            "imports": [],
        }
    }

    default_ranked = rank_candidates_bm25(files_map, ["user", "id"], min_score=0)
    overlay_ranked = rank_candidates_bm25(
        files_map,
        ["user", "id"],
        min_score=0,
        bm25_config={"score_scale": 1.0, "path_prior_factor": 0.0},
    )

    assert default_ranked and overlay_ranked
    assert default_ranked[0]["score"] > overlay_ranked[0]["score"]


def test_heuristic_and_chunk_scoring_overlay_changes_score_weights() -> None:
    files_map = {
        "src/service.py": {
            "language": "python",
            "module": "src.service",
            "symbols": [
                {"name": "process_user", "qualified_name": "src.service.process_user"}
            ],
            "imports": [],
        }
    }

    default_heur = rank_candidates_heuristic(files_map, ["service"], min_score=0)
    overlay_heur = rank_candidates_heuristic(
        files_map,
        ["service"],
        min_score=0,
        scoring_config={"path_exact": 8.0},
    )

    default_chunk_score, _ = score_chunk_candidate(
        path="src/service.py",
        module="src.service",
        qualified_name="src.service.process_user",
        name="process_user",
        signature="def process_user(user_id):",
        terms=["process_user"],
        file_score=1.0,
        reference_hits={},
    )
    overlay_chunk_score, overlay_breakdown = score_chunk_candidate(
        path="src/service.py",
        module="src.service",
        qualified_name="src.service.process_user",
        name="process_user",
        signature="def process_user(user_id):",
        terms=["process_user"],
        file_score=1.0,
        reference_hits={},
        scoring_config={"symbol_exact": 6.0},
    )

    assert overlay_heur[0]["score"] > default_heur[0]["score"]
    assert overlay_chunk_score > default_chunk_score
    assert overlay_breakdown["symbol"] == 6.0


def test_scip_scoring_overlay_changes_base_weight(tmp_path: Path) -> None:
    scip_path = tmp_path / "context-map" / "scip" / "index.json"
    scip_path.parent.mkdir(parents=True, exist_ok=True)
    scip_path.write_text(
        json.dumps(
            {
                "schema_version": "xref-json-1",
                "edges": [{"from": "src/a.py", "to": "src/b.py", "weight": 4}],
            }
        ),
        encoding="utf-8",
    )

    files_map = {
        "src/a.py": {"symbols": [], "references": []},
        "src/b.py": {"symbols": [], "references": []},
    }
    candidates = [
        {"path": "src/a.py", "score": 1.0, "score_breakdown": {}},
        {"path": "src/b.py", "score": 1.0, "score_breakdown": {}},
    ]

    default_boosted, default_payload = apply_scip_boost(
        index_path=scip_path,
        provider="xref_json",
        generate_fallback=False,
        files_map=files_map,
        candidates=[dict(item) for item in candidates],
        policy={"scip_weight": 1.0},
    )
    overlay_boosted, overlay_payload = apply_scip_boost(
        index_path=scip_path,
        provider="xref_json",
        generate_fallback=False,
        files_map=files_map,
        candidates=[dict(item) for item in candidates],
        policy={"scip_weight": 1.0},
        scoring_config={"base_weight": 2.0},
    )

    assert overlay_payload["weights"]["base_weight"] == 2.0
    assert overlay_boosted[0]["path"] == "src/b.py"
    assert overlay_boosted[0]["score"] > default_boosted[0]["score"]
    assert default_payload["weights"]["base_weight"] == 0.5
