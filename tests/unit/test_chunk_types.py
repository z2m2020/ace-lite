from ace_lite.chunking.types import (
    CONTEXTUAL_CHUNKING_SIDECAR_KEY,
    RETRIEVAL_CONTEXT_SIDECAR_KEY,
    ChunkCandidate,
    render_retrieval_context_from_sidecar,
    resolve_retrieval_context_text,
    strip_internal_chunk_sidecars,
)


def test_chunk_candidate_to_dict_omits_retrieval_context_by_default() -> None:
    candidate = ChunkCandidate(
        path="src/demo.py",
        qualified_name="pkg.demo.run",
        kind="function",
        lineno=10,
        end_lineno=18,
        score=1.2,
        signature="def run() -> None:",
        snippet="def run() -> None:\n    pass",
        retrieval_context="module=src.demo\nsymbol=pkg.demo.run",
    )

    payload = candidate.to_dict(include_signature=True, include_snippet=True)

    assert RETRIEVAL_CONTEXT_SIDECAR_KEY not in payload
    assert payload["signature"] == "def run() -> None:"
    assert payload["snippet"].startswith("def run()")


def test_chunk_candidate_to_dict_can_emit_internal_retrieval_context_sidecar() -> None:
    candidate = ChunkCandidate(
        path="src/demo.py",
        qualified_name="pkg.demo.run",
        kind="function",
        lineno=10,
        end_lineno=18,
        retrieval_context="module=src.demo\nsymbol=pkg.demo.run",
    )

    payload = candidate.to_dict(include_internal_sidecars=True)

    assert payload[RETRIEVAL_CONTEXT_SIDECAR_KEY] == candidate.retrieval_context


def test_strip_internal_chunk_sidecars_removes_all_internal_keys() -> None:
    chunks = [
        {
            "path": "src/demo.py",
            "qualified_name": "pkg.demo.run",
            "score": 1.0,
            CONTEXTUAL_CHUNKING_SIDECAR_KEY: {"schema_version": "v1"},
            RETRIEVAL_CONTEXT_SIDECAR_KEY: "module=src.demo",
            "_robust_signature_lite": {"available": True},
            "_topological_shield": {"enabled": True},
        }
    ]

    sanitized = strip_internal_chunk_sidecars(chunks)

    assert sanitized == [
        {
            "path": "src/demo.py",
            "qualified_name": "pkg.demo.run",
            "score": 1.0,
        }
    ]


def test_render_retrieval_context_from_sidecar_preserves_expected_text_shape() -> None:
    rendered = render_retrieval_context_from_sidecar(
        sidecar={
            "schema_version": "v1",
            "module": "src.demo",
            "language": "python",
            "kind": "method",
            "path": "src/demo.py",
            "symbol": "src.demo.Demo.run",
            "signature": "def run(token: str) -> bool:",
            "parent_symbol": "src.demo.Demo",
            "parent_signature": "class Demo:",
            "imports": ["from pkg.auth import validate"],
            "imports_truncated": False,
            "references": ["pkg.auth.validate"],
            "callees": ["pkg.auth.validate"],
            "callers": ["src.entry.bootstrap"],
            "references_truncated": False,
            "references_scope": "symbol_local_call",
        }
    )

    assert "module=src.demo" in rendered
    assert "language=python" in rendered
    assert "symbol=src.demo.Demo.run" in rendered
    assert "parent_symbol=src.demo.Demo" in rendered
    assert "parent=class Demo:" in rendered
    assert "imports=from pkg.auth import validate" in rendered
    assert "references=pkg.auth.validate" in rendered
    assert "callees=pkg.auth.validate" in rendered
    assert "callers=src.entry.bootstrap" in rendered
    assert "references_scope=symbol_local_call" in rendered


def test_resolve_retrieval_context_text_can_fall_back_to_structured_sidecar() -> None:
    payload = {
        "path": "src/demo.py",
        CONTEXTUAL_CHUNKING_SIDECAR_KEY: {
            "schema_version": "v1",
            "module": "src.demo",
            "language": "python",
            "symbol": "src.demo.run",
        },
    }

    resolved = resolve_retrieval_context_text(payload)

    assert resolved == "module=src.demo\nlanguage=python\nsymbol=src.demo.run"
