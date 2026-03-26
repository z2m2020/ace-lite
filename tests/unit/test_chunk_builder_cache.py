from __future__ import annotations

from ace_lite.chunking import builder as chunk_builder
from ace_lite.chunking.types import CONTEXTUAL_CHUNKING_SIDECAR_KEY


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


def test_build_candidate_chunks_attaches_internal_retrieval_context(
    tmp_path,
) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "demo.py").write_text(
        "from pkg.auth import validate\n\n"
        "class DemoService:\n"
        "    def run(self, token: str) -> bool:\n"
        "        return validate(token)\n",
        encoding="utf-8",
    )

    chunks, metrics = chunk_builder.build_candidate_chunks(
        root=str(tmp_path),
        files_map={
            "src/demo.py": {
                "module": "src.demo",
                "language": "python",
                "symbols": [
                    {
                        "kind": "class",
                        "name": "DemoService",
                        "qualified_name": "src.demo.DemoService",
                        "lineno": 3,
                        "end_lineno": 5,
                    },
                    {
                        "kind": "method",
                        "name": "run",
                        "qualified_name": "src.demo.DemoService.run",
                        "lineno": 4,
                        "end_lineno": 5,
                    },
                ],
                "references": [
                    {
                        "name": "validate",
                        "qualified_name": "pkg.auth.validate",
                        "lineno": 5,
                        "kind": "call",
                    },
                    {
                        "name": "build_service",
                        "qualified_name": "pkg.factory.build_service",
                        "lineno": 1,
                        "kind": "call",
                    }
                ],
                "imports": [
                    {
                        "type": "from",
                        "module": "pkg.auth",
                        "name": "validate",
                    }
                ],
            }
        },
        candidates=[{"path": "src/demo.py", "score": 3.0}],
        terms=["run", "token"],
        top_k_files=1,
        top_k_chunks=4,
        per_file_limit=2,
        token_budget=512,
        disclosure_mode="refs",
        snippet_max_lines=4,
        snippet_max_chars=240,
        policy={"chunk_weight": 1.0},
        tokenizer_model="gpt-4o-mini",
        diversity_enabled=False,
        diversity_path_penalty=0.0,
        diversity_symbol_family_penalty=0.0,
        diversity_kind_penalty=0.0,
        diversity_locality_penalty=0.0,
        diversity_locality_window=32,
    )

    method_chunk = next(
        item for item in chunks if item["qualified_name"] == "src.demo.DemoService.run"
    )
    retrieval_context = str(method_chunk.get("_retrieval_context") or "")
    contextual_sidecar = method_chunk.get(CONTEXTUAL_CHUNKING_SIDECAR_KEY)

    assert "module=src.demo" in retrieval_context
    assert "language=python" in retrieval_context
    assert "kind=method" in retrieval_context
    assert "symbol=src.demo.DemoService.run" in retrieval_context
    assert "parent_symbol=src.demo.DemoService" in retrieval_context
    assert "parent=class DemoService:" in retrieval_context
    assert "imports=from pkg.auth import validate" in retrieval_context
    assert "references=pkg.auth.validate" in retrieval_context
    assert "references_scope=symbol_local_call" in retrieval_context
    assert isinstance(contextual_sidecar, dict)
    assert contextual_sidecar["schema_version"] == "v1"
    assert contextual_sidecar["module"] == "src.demo"
    assert contextual_sidecar["language"] == "python"
    assert contextual_sidecar["kind"] == "method"
    assert contextual_sidecar["symbol"] == "src.demo.DemoService.run"
    assert contextual_sidecar["parent_symbol"] == "src.demo.DemoService"
    assert contextual_sidecar["parent_signature"] == "class DemoService:"
    assert contextual_sidecar["imports"] == ["from pkg.auth import validate"]
    assert contextual_sidecar["imports_truncated"] is False
    assert contextual_sidecar["references"] == ["pkg.auth.validate"]
    assert contextual_sidecar["references_scope"] == "symbol_local_call"
    assert contextual_sidecar["references_truncated"] is False
    assert metrics["retrieval_context_chunk_count"] == 2.0
    assert metrics["retrieval_context_coverage_ratio"] == 1.0
    assert metrics["retrieval_context_char_count_mean"] > 0.0
    assert metrics["contextual_sidecar_parent_symbol_chunk_count"] == 2.0
    assert metrics["contextual_sidecar_parent_symbol_coverage_ratio"] == 1.0
    assert metrics["contextual_sidecar_reference_hint_chunk_count"] == 2.0
    assert metrics["contextual_sidecar_reference_hint_coverage_ratio"] == 1.0


def test_build_candidate_chunks_uses_symbol_local_go_call_references(
    tmp_path,
) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "service.go").write_text(
        "package service\n\n"
        "func helper() {}\n\n"
        "func Bootstrap() {\n"
        "    Handle()\n"
        "}\n\n"
        "func Handle() {\n"
        "    helper()\n"
        "    repo.Save()\n"
        "}\n",
        encoding="utf-8",
    )

    chunks, _ = chunk_builder.build_candidate_chunks(
        root=str(tmp_path),
        files_map={
            "src/service.go": {
                "module": "src.service",
                "language": "go",
                "symbols": [
                    {
                        "kind": "function",
                        "name": "helper",
                        "qualified_name": "src.service.helper",
                        "lineno": 3,
                        "end_lineno": 3,
                    },
                    {
                        "kind": "function",
                        "name": "Bootstrap",
                        "qualified_name": "src.service.Bootstrap",
                        "lineno": 5,
                        "end_lineno": 7,
                    },
                    {
                        "kind": "function",
                        "name": "Handle",
                        "qualified_name": "src.service.Handle",
                        "lineno": 9,
                        "end_lineno": 12,
                    }
                ],
                "references": [
                    {
                        "name": "Handle",
                        "qualified_name": "src.service.Handle",
                        "lineno": 6,
                        "kind": "call",
                    },
                    {
                        "name": "helper",
                        "qualified_name": "src.service.helper",
                        "lineno": 10,
                        "kind": "call",
                    },
                    {
                        "name": "Save",
                        "qualified_name": "repo.Save",
                        "lineno": 11,
                        "kind": "call",
                    },
                    {
                        "name": "ignored",
                        "qualified_name": "repo.Ignored",
                        "lineno": 3,
                        "kind": "call",
                    },
                ],
                "imports": [],
            }
        },
        candidates=[{"path": "src/service.go", "score": 2.0}],
        terms=["handle"],
        top_k_files=1,
        top_k_chunks=2,
        per_file_limit=2,
        token_budget=256,
        disclosure_mode="refs",
        snippet_max_lines=4,
        snippet_max_chars=240,
        policy={"chunk_weight": 1.0},
        tokenizer_model="gpt-4o-mini",
        diversity_enabled=False,
        diversity_path_penalty=0.0,
        diversity_symbol_family_penalty=0.0,
        diversity_kind_penalty=0.0,
        diversity_locality_penalty=0.0,
        diversity_locality_window=32,
    )

    handle_chunk = next(
        item for item in chunks if item["qualified_name"] == "src.service.Handle"
    )
    contextual_sidecar = handle_chunk.get(CONTEXTUAL_CHUNKING_SIDECAR_KEY)

    assert isinstance(contextual_sidecar, dict)
    assert contextual_sidecar["references"] == ["src.service.helper", "repo.Save"]
    assert contextual_sidecar["references_scope"] == "symbol_local_call"
    assert contextual_sidecar["callees"] == ["src.service.helper"]
    assert contextual_sidecar["callers"] == ["src.service.Bootstrap"]
