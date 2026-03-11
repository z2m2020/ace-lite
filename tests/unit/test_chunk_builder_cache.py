from __future__ import annotations

from ace_lite.chunking import builder as chunk_builder


def _sample_files_map() -> dict[str, dict[str, object]]:
    return {
        "src/demo.py": {
            "module": "src.demo",
            "symbols": [
                {
                    "kind": "function",
                    "name": "demo_fn",
                    "qualified_name": "demo_fn",
                    "lineno": 1,
                    "end_lineno": 2,
                }
            ],
            "references": [{"name": "demo_fn", "qualified_name": "demo_fn"}],
        }
    }


def _sample_candidates() -> list[dict[str, object]]:
    return [{"path": "src/demo.py", "score": 3.0}]


def test_build_candidate_chunks_reference_hits_cache_reuses_same_key(
    monkeypatch,
) -> None:
    chunk_builder._REFERENCE_HITS_CACHE.clear()
    files_map = _sample_files_map()
    candidates = _sample_candidates()
    calls = {"count": 0}

    original = chunk_builder._build_reference_hits

    def counting_build_reference_hits(
        map_payload: dict[str, dict[str, object]],
    ) -> dict[str, int]:
        calls["count"] += 1
        return original(map_payload)

    monkeypatch.setattr(
        chunk_builder,
        "_build_reference_hits",
        counting_build_reference_hits,
    )

    kwargs = {
        "root": ".",
        "files_map": files_map,
        "candidates": candidates,
        "terms": ["demo_fn"],
        "top_k_files": 1,
        "top_k_chunks": 2,
        "per_file_limit": 1,
        "token_budget": 256,
        "disclosure_mode": "refs",
        "snippet_max_lines": 3,
        "snippet_max_chars": 200,
        "policy": {"chunk_weight": 1.0},
        "tokenizer_model": "gpt-4o-mini",
        "diversity_enabled": False,
        "diversity_path_penalty": 0.0,
        "diversity_symbol_family_penalty": 0.0,
        "diversity_kind_penalty": 0.0,
        "diversity_locality_penalty": 0.0,
        "diversity_locality_window": 32,
        "reference_hits_cache_key": "index-hash-demo",
    }

    chunks_first, _ = chunk_builder.build_candidate_chunks(**kwargs)
    chunks_second, _ = chunk_builder.build_candidate_chunks(**kwargs)

    assert chunks_first
    assert chunks_second
    assert calls["count"] == 1


def test_build_candidate_chunks_reference_hits_cache_miss_on_different_key(
    monkeypatch,
) -> None:
    chunk_builder._REFERENCE_HITS_CACHE.clear()
    files_map = _sample_files_map()
    candidates = _sample_candidates()
    calls = {"count": 0}

    original = chunk_builder._build_reference_hits

    def counting_build_reference_hits(
        map_payload: dict[str, dict[str, object]],
    ) -> dict[str, int]:
        calls["count"] += 1
        return original(map_payload)

    monkeypatch.setattr(
        chunk_builder,
        "_build_reference_hits",
        counting_build_reference_hits,
    )

    base_kwargs = {
        "root": ".",
        "files_map": files_map,
        "candidates": candidates,
        "terms": ["demo_fn"],
        "top_k_files": 1,
        "top_k_chunks": 2,
        "per_file_limit": 1,
        "token_budget": 256,
        "disclosure_mode": "refs",
        "snippet_max_lines": 3,
        "snippet_max_chars": 200,
        "policy": {"chunk_weight": 1.0},
        "tokenizer_model": "gpt-4o-mini",
        "diversity_enabled": False,
        "diversity_path_penalty": 0.0,
        "diversity_symbol_family_penalty": 0.0,
        "diversity_kind_penalty": 0.0,
        "diversity_locality_penalty": 0.0,
        "diversity_locality_window": 32,
    }

    chunk_builder.build_candidate_chunks(
        **base_kwargs, reference_hits_cache_key="index-hash-a"
    )
    chunk_builder.build_candidate_chunks(
        **base_kwargs, reference_hits_cache_key="index-hash-b"
    )

    assert calls["count"] == 2
