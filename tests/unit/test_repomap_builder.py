from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ace_lite.repomap.builder import (
    build_repo_map,
    build_stage_precompute_payload,
    build_stage_repo_map,
    write_repo_map,
)
from ace_lite.repomap.ranking import (
    _collect_file_stats,
    _graph_scores,
    _reference_candidates,
    rank_index_files,
)


def test_rank_index_files_orders_by_score(fake_index_files: dict[str, dict[str, Any]]) -> None:
    ranked = rank_index_files(files=fake_index_files)

    assert ranked[0]["path"] == "src/a.py"
    assert ranked[1]["path"] == "src/b.py"


def test_rank_index_files_graph_profile(fake_index_files: dict[str, dict[str, Any]]) -> None:
    ranked = rank_index_files(files=fake_index_files, profile="graph")

    assert ranked[0]["ranking_profile"] == "graph"
    assert "graph_rank" in ranked[0]
    assert "import_depth_rank" in ranked[0]


def test_rank_index_files_graph_profile_deterministic_fields_and_order() -> None:
    files = {
        "src/b.py": {
            "module": "src.b",
            "language": "python",
            "symbols": [],
            "imports": [],
        },
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [],
            "imports": [],
        },
    }

    ranked = rank_index_files(files=files, profile="graph")  # type: ignore[arg-type]

    assert [item["path"] for item in ranked] == ["src/a.py", "src/b.py"]
    assert ranked[0]["score"] == ranked[1]["score"]
    assert ranked[0]["graph_rank"] == ranked[1]["graph_rank"]
    assert ranked[0]["import_depth_rank"] == ranked[1]["import_depth_rank"]


def test_rank_index_files_graph_profile_custom_signal_weights() -> None:
    files = {
        "src/c.py": {
            "module": "src.c",
            "language": "python",
            "symbols": [{"name": "C"}],
            "imports": [{"module": "src.a"}],
        },
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [{"name": "A"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "module": "src.b",
            "language": "python",
            "symbols": [{"name": "B"}],
            "imports": [],
        },
    }

    ranked_default = rank_index_files(files=files, profile="graph")  # type: ignore[arg-type]
    ranked_import_depth = rank_index_files(
        files=files,
        profile="graph",
        signal_weights={"base": 0.0, "graph": 0.0, "import_depth": 1.0},
    )  # type: ignore[arg-type]

    assert ranked_default[0]["path"] == "src/a.py"
    assert ranked_import_depth[0]["path"] == "src/b.py"
    assert ranked_default[0]["path"] != ranked_import_depth[0]["path"]
    assert ranked_import_depth[0]["score"] > ranked_import_depth[1]["score"]
    assert ranked_import_depth[1]["score"] > ranked_import_depth[2]["score"]


def test_rank_index_files_rejects_unknown_profile(fake_index_files: dict[str, dict[str, Any]]) -> None:
    with pytest.raises(ValueError, match="unsupported ranking profile"):
        rank_index_files(files=fake_index_files, profile="unknown")


def test_build_repo_map_respects_budget(fake_index_files: dict[str, dict[str, Any]]) -> None:
    repo_map = build_repo_map(index_payload={"files": fake_index_files}, budget_tokens=6, top_k=10)

    assert repo_map["selected_count"] >= 1
    assert repo_map["used_tokens"] <= 6
    assert repo_map["markdown"].startswith("# Repo Map")


def test_build_repo_map_graph_profile(fake_index_files: dict[str, dict[str, Any]]) -> None:
    repo_map = build_repo_map(
        index_payload={"files": fake_index_files},
        budget_tokens=100,
        top_k=10,
        ranking_profile="graph",
    )

    assert repo_map["ranking_profile"] == "graph"
    assert repo_map["selected_count"] >= 1


def test_build_repo_map_passes_signal_weights() -> None:
    files = {
        "src/c.py": {
            "module": "src.c",
            "language": "python",
            "symbols": [{"name": "C"}],
            "imports": [{"module": "src.a"}],
        },
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [{"name": "A"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "module": "src.b",
            "language": "python",
            "symbols": [{"name": "B"}],
            "imports": [],
        },
    }
    repo_map = build_repo_map(
        index_payload={"files": files},
        budget_tokens=100,
        top_k=1,
        ranking_profile="graph",
        signal_weights={"base": 0.0, "graph": 0.0, "import_depth": 1.0},
    )

    assert repo_map["files"][0]["path"] == "src/b.py"


def test_write_repo_map_outputs_json_and_markdown(tmp_path: Path, fake_index_files: dict[str, dict[str, Any]]) -> None:
    out_json = tmp_path / "context-map" / "repo_map.json"
    out_md = tmp_path / "context-map" / "repo_map.md"

    outputs = write_repo_map(
        index_payload={"files": fake_index_files},
        output_json=out_json,
        output_md=out_md,
        budget_tokens=100,
        top_k=10,
        ranking_profile="graph",
    )

    assert Path(outputs["repo_map_json"]).exists()
    assert Path(outputs["repo_map_md"]).exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "markdown" not in payload
    assert payload["selected_count"] >= 1
    assert payload["ranking_profile"] == "graph"


def test_rank_index_files_graph_profile_includes_reference_rank(fake_index_files: dict[str, dict[str, Any]]) -> None:
    ranked = rank_index_files(files=fake_index_files, profile='graph')
    assert 'reference_rank' in ranked[0]


def test_rank_index_files_graph_profile_reference_signal() -> None:
    files = {
        'src/defs/foo.py': {
            'module': 'src.defs.foo',
            'language': 'python',
            'symbols': [{'name': 'Foo', 'qualified_name': 'src.defs.foo.Foo'}],
            'imports': [],
            'references': [],
        },
        'src/defs/bar.py': {
            'module': 'src.defs.bar',
            'language': 'python',
            'symbols': [{'name': 'Bar', 'qualified_name': 'src.defs.bar.Bar'}],
            'imports': [],
            'references': [],
        },
        'src/use_one.py': {
            'module': 'src.use_one',
            'language': 'python',
            'symbols': [],
            'imports': [],
            'references': [{'name': 'Foo', 'qualified_name': 'src.defs.foo.Foo'}],
        },
        'src/use_two.py': {
            'module': 'src.use_two',
            'language': 'python',
            'symbols': [],
            'imports': [],
            'references': [{'name': 'Foo', 'qualified_name': 'src.defs.foo.Foo'}],
        },
        'src/use_three.py': {
            'module': 'src.use_three',
            'language': 'python',
            'symbols': [],
            'imports': [],
            'references': [{'name': 'Bar', 'qualified_name': 'src.defs.bar.Bar'}],
        },
    }

    ranked = rank_index_files(
        files=files,
        profile='graph',
        signal_weights={'base': 0.0, 'graph': 0.0, 'import_depth': 0.0, 'reference': 1.0},
    )  # type: ignore[arg-type]

    foo = next(item for item in ranked if item['path'] == 'src/defs/foo.py')
    bar = next(item for item in ranked if item['path'] == 'src/defs/bar.py')
    assert ranked[0]['path'] == 'src/defs/foo.py'
    assert foo['reference_rank'] > bar['reference_rank']


def test_rank_index_files_graph_profile_reference_kind_weighting() -> None:
    files = {
        "src/defs/foo.py": {
            "module": "src.defs.foo",
            "language": "python",
            "symbols": [{"name": "Foo", "qualified_name": "src.defs.foo.Foo"}],
            "imports": [],
            "references": [],
        },
        "src/defs/bar.py": {
            "module": "src.defs.bar",
            "language": "python",
            "symbols": [{"name": "Bar", "qualified_name": "src.defs.bar.Bar"}],
            "imports": [],
            "references": [],
        },
        "src/use_mixed.py": {
            "module": "src.use_mixed",
            "language": "python",
            "symbols": [],
            "imports": [],
            "references": [
                {
                    "name": "Foo",
                    "qualified_name": "src.defs.foo.Foo",
                    "kind": "call",
                },
                {
                    "name": "Bar",
                    "qualified_name": "src.defs.bar.Bar",
                    "kind": "reference",
                }
            ],
        },
    }

    ranked = rank_index_files(
        files=files,
        profile="graph",
        signal_weights={"base": 0.0, "graph": 0.0, "import_depth": 0.0, "reference": 1.0},
    )  # type: ignore[arg-type]
    foo = next(item for item in ranked if item["path"] == "src/defs/foo.py")
    bar = next(item for item in ranked if item["path"] == "src/defs/bar.py")

    assert foo["reference_rank"] > bar["reference_rank"]


def test_rank_index_files_graph_profile_reference_absent_compatibility() -> None:
    files = {
        'src/a.py': {'module': 'src.a', 'language': 'python', 'symbols': [], 'imports': []},
        'src/b.py': {'module': 'src.b', 'language': 'python', 'symbols': [], 'imports': []},
    }

    ranked = rank_index_files(files=files, profile='graph')  # type: ignore[arg-type]
    assert [item['path'] for item in ranked] == ['src/a.py', 'src/b.py']
    assert ranked[0]['reference_rank'] == ranked[1]['reference_rank']


def test_collect_file_stats_dedupes_hot_lists() -> None:
    stats, _ = _collect_file_stats(
        {
            'src/a.py': {
                'module': 'src.a',
                'language': 'python',
                'symbols': [
                    {'name': 'Foo', 'qualified_name': 'src.a.Foo'},
                    {'name': 'Foo', 'qualified_name': 'src.a.Foo'},
                ],
                'imports': [
                    {'module': 'src.b'},
                    {'module': 'src.b'},
                ],
                'references': [
                    {'name': 'Foo', 'qualified_name': 'src.a.Foo'},
                    {'name': 'Foo', 'qualified_name': 'src.a.Foo'},
                ],
            }
        }
    )

    a = stats['src/a.py']
    assert a['import_modules'] == ['src.b']
    assert a['symbol_keys'] == ['src.a.Foo', 'Foo']
    assert a['references'] == ['src.a.Foo', 'Foo']


def test_reference_candidates_dedupes_tail_symbol() -> None:
    assert _reference_candidates('Foo') == ('Foo',)
    assert _reference_candidates('src.a.Foo') == ('src.a.Foo', 'Foo')


def test_graph_scores_distributes_sink_mass_once() -> None:
    ranks = _graph_scores(
        nodes=['a', 'b', 'c'],
        edges={
            'a': ('b',),
            'b': (),
            'c': (),
        },
    )

    assert sum(ranks.values()) == pytest.approx(1.0)
    assert ranks['b'] > ranks['a']
    assert ranks['b'] > ranks['c']



def test_rank_index_files_graph_seeded_prioritizes_seed_paths() -> None:
    files = {
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [{"name": "A"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "module": "src.b",
            "language": "python",
            "symbols": [{"name": "B"}],
            "imports": [],
        },
        "src/x.py": {
            "module": "src.x",
            "language": "python",
            "symbols": [{"name": "X"}],
            "imports": [{"module": "src.y"}],
        },
        "src/y.py": {
            "module": "src.y",
            "language": "python",
            "symbols": [{"name": "Y"}],
            "imports": [],
        },
    }

    ranked_default = rank_index_files(files=files, profile="graph")  # type: ignore[arg-type]
    ranked_seeded = rank_index_files(
        files=files,
        profile="graph_seeded",
        seed_paths=["src/x.py"],
    )  # type: ignore[arg-type]

    assert ranked_default[0]["path"] == "src/a.py"
    assert ranked_seeded[0]["path"] == "src/x.py"
    assert ranked_seeded[0]["seeded"] is True


def test_build_stage_repo_map_graph_seeded_tracks_seed_hints() -> None:
    files = {
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [{"name": "A"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "module": "src.b",
            "language": "python",
            "symbols": [{"name": "B"}],
            "imports": [],
        },
        "src/x.py": {
            "module": "src.x",
            "language": "python",
            "symbols": [{"name": "X"}],
            "imports": [{"module": "src.y"}],
        },
        "src/y.py": {
            "module": "src.y",
            "language": "python",
            "symbols": [{"name": "Y"}],
            "imports": [],
        },
    }

    payload = build_stage_repo_map(
        index_files=files,
        seed_candidates=[{"path": "src/x.py", "score": 3.0}],
        ranking_profile="graph_seeded",
        top_k=2,
        neighbor_limit=2,
        budget_tokens=256,
    )

    assert payload["ranking_profile"] == "graph_seeded"
    assert payload["seed_hint_count"] == 1
    assert payload["seed_paths"]
    assert payload["seed_paths"][0] == "src/x.py"


def test_build_stage_repo_map_collects_tags_and_render_levels() -> None:
    files = {
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [
                {
                    "name": "Alpha",
                    "qualified_name": "src.a.Alpha",
                    "kind": "class",
                    "lineno": 3,
                    "end_lineno": 21,
                },
                {
                    "name": "run",
                    "qualified_name": "src.a.run",
                    "kind": "function",
                    "lineno": 24,
                    "end_lineno": 36,
                },
            ],
            "imports": [],
        }
    }

    payload = build_stage_repo_map(
        index_files=files,
        seed_candidates=[{"path": "src/a.py", "score": 2.0}],
        top_k=1,
        neighbor_limit=0,
        budget_tokens=24,
    )

    assert payload["tag_summary"]["total_tags"] >= 2
    assert sum(int(value) for value in payload["render_levels"].values()) >= 1
    assert payload["files"][0]["tag_count"] >= 2
    assert payload["files"][0]["tags"][0]["signature"]


def test_build_stage_repo_map_renders_graph_context_summary() -> None:
    files = {
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [{"name": "A"}],
            "imports": [],
        },
        "src/b.py": {
            "module": "src.b",
            "language": "python",
            "symbols": [{"name": "B"}],
            "imports": [],
        },
    }

    payload = build_stage_repo_map(
        index_files=files,
        seed_candidates=[{"path": "src/a.py", "score": 2.0}],
        subgraph_payload={
            "enabled": True,
            "reason": "ok",
            "seed_paths": ["src/a.py", "src/b.py"],
            "edge_counts": {"graph_lookup": 2, "graph_prior": 1},
        },
        top_k=1,
        neighbor_limit=0,
        budget_tokens=128,
    )

    assert "## Graph Context" in payload["markdown"]
    assert "- seed_paths: src/a.py, src/b.py" in payload["markdown"]
    assert "- edge_type_count: 2" in payload["markdown"]
    assert "- edge_total_count: 3" in payload["markdown"]
    assert "- edge_counts: graph_lookup=2, graph_prior=1" in payload["markdown"]


def test_build_stage_repo_map_uses_subgraph_seed_paths_when_seed_candidates_missing() -> None:
    files = {
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [{"name": "A"}, {"name": "AnotherA"}],
            "imports": [],
        },
        "src/b.py": {
            "module": "src.b",
            "language": "python",
            "symbols": [{"name": "B"}],
            "imports": [],
        },
    }

    payload = build_stage_repo_map(
        index_files=files,
        seed_candidates=[],
        subgraph_payload={
            "enabled": True,
            "reason": "ok",
            "seed_paths": ["src/b.py"],
            "edge_counts": {"graph_lookup": 1},
        },
        top_k=1,
        neighbor_limit=0,
        budget_tokens=128,
    )

    assert payload["seed_paths"] == ["src/b.py"]
    assert payload["explainability"]["seed_strategy"] == "subgraph_payload"
    assert payload["explainability"]["seed_sources"] == [
        {"path": "src/b.py", "source": "subgraph_seed"}
    ]
    assert "seed_strategy:subgraph_payload" in payload["explainability"]["selection_notes"]
    assert "subgraph_seed_paths_present" in payload["explainability"]["selection_notes"]


def test_build_stage_repo_map_neighbor_depth_two_hops() -> None:
    files = {
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [{"name": "A"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "module": "src.b",
            "language": "python",
            "symbols": [{"name": "B"}],
            "imports": [{"module": "src.c"}],
        },
        "src/c.py": {
            "module": "src.c",
            "language": "python",
            "symbols": [{"name": "C"}],
            "imports": [],
        },
    }

    depth_one = build_stage_repo_map(
        index_files=files,
        seed_candidates=[{"path": "src/a.py", "score": 1.0}],
        top_k=1,
        neighbor_limit=4,
        neighbor_depth=1,
        budget_tokens=512,
    )
    depth_two = build_stage_repo_map(
        index_files=files,
        seed_candidates=[{"path": "src/a.py", "score": 1.0}],
        top_k=1,
        neighbor_limit=4,
        neighbor_depth=2,
        budget_tokens=512,
    )

    assert depth_one["neighbor_paths"] == ["src/b.py"]
    assert depth_two["neighbor_paths"] == ["src/b.py", "src/c.py"]
    assert depth_two["neighbor_depth"] == 2


def test_build_stage_repo_map_prefers_local_path_style_candidate() -> None:
    files = {
        "src/core/main.py": {
            "module": "src.core.main",
            "language": "python",
            "symbols": [{"name": "main", "qualified_name": "src.core.main.main"}],
            "imports": [{"module": "app"}],
        },
        "src/core/app.py": {
            "module": "src.core.app",
            "language": "python",
            "symbols": [{"name": "App", "qualified_name": "src.core.app.App"}],
            "imports": [],
        },
        "tests/app.py": {
            "module": "tests.app",
            "language": "python",
            "symbols": [{"name": "App", "qualified_name": "tests.app.App"}],
            "imports": [],
        },
    }

    direct = build_stage_repo_map(
        index_files=files,
        seed_candidates=[{"path": "src/core/main.py", "score": 10.0}],
        top_k=1,
        neighbor_limit=4,
        neighbor_depth=1,
        budget_tokens=512,
    )
    precomputed = build_stage_precompute_payload(
        index_files=files,
        ranking_profile="graph",
    )
    from_precomputed = build_stage_repo_map(
        index_files=files,
        seed_candidates=[{"path": "src/core/main.py", "score": 10.0}],
        top_k=1,
        neighbor_limit=4,
        neighbor_depth=1,
        budget_tokens=512,
        precomputed_payload=precomputed,
    )

    assert direct["expected_neighbor_paths"] == ["src/core/app.py"]
    assert direct["neighbor_paths"] == ["src/core/app.py"]
    assert direct["explainability"]["seed_strategy"] == "seed_candidates"
    assert direct["explainability"]["ambiguity"]["path_style_collision_count"] >= 1
    assert "path_style_collisions:1" in direct["explainability"]["selection_notes"]
    assert from_precomputed["expected_neighbor_paths"] == ["src/core/app.py"]
    assert from_precomputed["neighbor_paths"] == ["src/core/app.py"]
    assert from_precomputed["explainability"]["ambiguity"]["path_style_collision_count"] >= 1


def test_build_stage_repo_map_includes_reference_neighbors() -> None:
    files = {
        "src/defs/foo.py": {
            "module": "src.defs.foo",
            "language": "python",
            "symbols": [{"name": "Foo", "qualified_name": "Foo"}],
            "imports": [],
            "references": [],
        },
        "src/use.py": {
            "module": "src.use",
            "language": "python",
            "symbols": [],
            "imports": [],
            "references": [{"name": "Foo", "qualified_name": "Foo", "kind": "call"}],
        },
    }

    payload = build_stage_repo_map(
        index_files=files,
        seed_candidates=[{"path": "src/use.py", "score": 10.0}],
        top_k=1,
        neighbor_limit=4,
        neighbor_depth=1,
        budget_tokens=512,
    )

    assert payload["expected_neighbor_paths"] == []
    assert payload["reference_neighbor_paths"] == ["src/defs/foo.py"]
    assert payload["neighbor_paths"] == ["src/defs/foo.py"]
    assert payload["explainability"]["neighbor_sources"]["reference_candidate_count"] == 1
    assert (
        payload["explainability"]["neighbor_sources"]["included_reference_count"] == 1
    )
    assert "reference_neighbors_present" in payload["explainability"]["selection_notes"]


def test_build_stage_repo_map_reserves_budget_for_neighbors(monkeypatch: pytest.MonkeyPatch) -> None:
    def _stub_estimate_tokens(text: str, *, model: str | None = None) -> int:
        _ = model
        value = str(text)
        if value.startswith("# RepoMap Skeleton"):
            return 1
        if value.startswith("## One-Hop Neighbors"):
            return 1
        if value.startswith("###") and "[seed]" in value:
            if "- imports:" in value:
                return 6
            return 4
        if value.startswith("###") and "[neighbor]" in value:
            return 5
        if value.startswith("- `") and "[seed]" in value:
            return 2
        if value.startswith("- `") and "[neighbor]" in value:
            return 2
        return 1

    def _stub_rank_index_files(
        *,
        files: dict[str, Any],
        profile: str,
        signal_weights: Any = None,
        seed_paths: Any = None,
    ) -> list[dict[str, Any]]:
        _ = (files, profile, signal_weights, seed_paths)
        return [
            {"path": "src/a.py", "score": 3.0, "module": "src.a", "language": "python"},
            {"path": "src/x.py", "score": 2.0, "module": "src.x", "language": "python"},
            {"path": "src/b.py", "score": 1.0, "module": "src.b", "language": "python"},
        ]

    monkeypatch.setattr("ace_lite.repomap.builder.estimate_tokens", _stub_estimate_tokens)
    monkeypatch.setattr("ace_lite.repomap.builder.rank_index_files", _stub_rank_index_files)

    files = {
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [{"name": "A", "qualified_name": "src.a.A", "kind": "class"}],
            "imports": [{"module": "src.b"}],
        },
        "src/x.py": {
            "module": "src.x",
            "language": "python",
            "symbols": [{"name": "X", "qualified_name": "src.x.X", "kind": "class"}],
            "imports": [],
        },
        "src/b.py": {
            "module": "src.b",
            "language": "python",
            "symbols": [{"name": "B", "qualified_name": "src.b.B", "kind": "class"}],
            "imports": [],
        },
    }

    payload = build_stage_repo_map(
        index_files=files,
        seed_candidates=[
            {"path": "src/a.py", "score": 3.0},
            {"path": "src/x.py", "score": 2.0},
        ],
        top_k=2,
        neighbor_limit=4,
        neighbor_depth=1,
        budget_tokens=10,
    )

    assert payload["seed_paths"] == ["src/a.py", "src/x.py"]
    assert payload["expected_neighbor_paths"] == ["src/b.py"]
    assert payload["neighbor_paths"] == ["src/b.py"]
    assert payload["dependency_recall"]["hit_rate"] == 1.0
    assert "## One-Hop Neighbors" in payload["markdown"]
    assert "src/b.py" in payload["markdown"]
    assert (
        payload["explainability"]["neighbor_sources"]["import_candidate_count"] == 1
    )
    assert "budget_trimmed_neighbors" not in payload["explainability"]["selection_notes"]


def test_build_stage_repo_map_explainability_tracks_ranked_fallback_seeds() -> None:
    files = {
        "src/a.py": {
            "module": "src.a",
            "language": "python",
            "symbols": [{"name": "A"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "module": "src.b",
            "language": "python",
            "symbols": [{"name": "B"}],
            "imports": [],
        },
    }

    payload = build_stage_repo_map(
        index_files=files,
        seed_candidates=[],
        top_k=1,
        neighbor_limit=2,
        neighbor_depth=1,
        budget_tokens=128,
    )

    assert payload["seed_paths"] == ["src/a.py"]
    assert payload["explainability"]["seed_strategy"] == "ranked_fallback"
    assert payload["explainability"]["seed_sources"] == [
        {"path": "src/a.py", "source": "ranked_fallback"}
    ]
    assert "seed_strategy:ranked_fallback" in payload["explainability"]["selection_notes"]
