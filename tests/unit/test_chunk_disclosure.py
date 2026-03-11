from __future__ import annotations

import textwrap
from pathlib import Path

from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig


def _seed_repo(root: Path) -> None:
    (root / "src" / "core").mkdir(parents=True, exist_ok=True)
    (root / "src" / "core" / "auth.py").write_text(
        textwrap.dedent(
            """
            def validate_token(raw: str) -> bool:
                return bool(raw)


            def refresh_session(token: str) -> str:
                token = token.strip()
                return token
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def test_chunk_disclosure_controls_signature_and_snippet_payload(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    _seed_repo(tmp_path)

    base_config = {
        "skills": {"manifest": fake_skill_manifest},
        "index": {
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        "repomap": {"enabled": False},
        "cochange": {"enabled": False},
        "scip": {"enabled": False},
        "chunking": {
            "top_k": 6,
            "per_file_limit": 3,
            "token_budget": 99999,
        },
    }

    refs = AceOrchestrator(
        config=OrchestratorConfig(
            **{
                **base_config,
                "chunking": {**base_config["chunking"], "disclosure": "refs"},
            }
        ),
    ).plan(
        query="validate token behavior",
        repo="demo",
        root=str(tmp_path),
    )
    signature = AceOrchestrator(
        config=OrchestratorConfig(
            **{
                **base_config,
                "chunking": {**base_config["chunking"], "disclosure": "signature"},
            }
        ),
    ).plan(
        query="validate token behavior",
        repo="demo",
        root=str(tmp_path),
    )
    snippet = AceOrchestrator(
        config=OrchestratorConfig(
            **{
                **base_config,
                "chunking": {
                    **base_config["chunking"],
                    "disclosure": "snippet",
                    "snippet_max_lines": 2,
                    "snippet_max_chars": 60,
                },
            }
        ),
    ).plan(
        query="validate token behavior",
        repo="demo",
        root=str(tmp_path),
    )

    refs_chunks = refs["index"]["candidate_chunks"]
    signature_chunks = signature["index"]["candidate_chunks"]
    snippet_chunks = snippet["index"]["candidate_chunks"]

    assert refs_chunks
    assert signature_chunks
    assert snippet_chunks

    assert all("signature" not in item and "snippet" not in item for item in refs_chunks)
    assert any(
        isinstance(item.get("robust_signature_summary"), dict)
        and item["robust_signature_summary"].get("available", False)
        for item in refs_chunks
    )
    assert all("_robust_signature_lite" not in item for item in refs_chunks)
    assert all(
        "entity_vocab" not in (item.get("robust_signature_summary") or {})
        for item in refs_chunks
    )
    assert any(str(item.get("signature") or "").strip() for item in signature_chunks)
    assert any(str(item.get("snippet") or "").strip() for item in snippet_chunks)

    first_snippet = next(
        str(item.get("snippet") or "") for item in snippet_chunks if str(item.get("snippet") or "").strip()
    )
    assert len(first_snippet) <= 60
    assert len(first_snippet.splitlines()) <= 2

    refs_used = float(refs["index"]["chunk_metrics"].get("chunk_budget_used", 0.0) or 0.0)
    sig_used = float(signature["index"]["chunk_metrics"].get("chunk_budget_used", 0.0) or 0.0)
    snippet_used = float(snippet["index"]["chunk_metrics"].get("chunk_budget_used", 0.0) or 0.0)

    assert refs_used <= sig_used <= snippet_used
    assert refs["index"]["chunk_metrics"]["robust_signature_count"] >= 1.0
    assert refs["index"]["metadata"]["robust_signature_count"] >= 1

def test_snippet_context_expansion_includes_class_and_imports(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    (tmp_path / "src" / "core").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "core" / "auth.py").write_text(
        textwrap.dedent(
            """
            import jwt
            from typing import Any

            class SessionManager:
                def __init__(self):
                    pass

                def refresh_session(self, token: str) -> str:
                    token = token.strip()
                    return token
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    base_config = {
        "skills": {"manifest": fake_skill_manifest},
        "index": {
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        "repomap": {"enabled": False},
        "cochange": {"enabled": False},
        "scip": {"enabled": False},
        "chunking": {
            "top_k": 6,
            "per_file_limit": 3,
            "token_budget": 99999,
            "disclosure": "snippet",
            "snippet_max_lines": 5,
            "snippet_max_chars": 200,
        },
    }

    result = AceOrchestrator(
        config=OrchestratorConfig(**base_config),
    ).plan(
        query="refresh session logic",
        repo="demo",
        root=str(tmp_path),
    )

    chunks = result["index"]["candidate_chunks"]
    
    # Check if we got the method chunk
    method_chunk = next(
        (c for c in chunks if c.get("qualified_name") == "SessionManager.refresh_session"),
        None
    )
    assert method_chunk is not None
    
    snippet = method_chunk.get("snippet", "")
    assert len(snippet.splitlines()) <= 5
    assert "# Context: class SessionManager:" in snippet
    assert "# Imports: import jwt, from typing import Any" in snippet
    assert "def refresh_session" in snippet


def test_snippet_context_expansion_respects_tiny_line_budgets(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    (tmp_path / "src" / "core").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "core" / "auth.py").write_text(
        textwrap.dedent(
            """
            import jwt
            from typing import Any

            class SessionManager:
                def __init__(self):
                    pass

                def refresh_session(self, token: str) -> str:
                    token = token.strip()
                    return token
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    for max_lines in (1, 2):
        result = AceOrchestrator(
            config=OrchestratorConfig(
                skills={"manifest": fake_skill_manifest},
                index={
                    "languages": ["python"],
                    "cache_path": tmp_path / "context-map" / f"index-{max_lines}.json",
                },
                repomap={"enabled": False},
                cochange={"enabled": False},
                scip={"enabled": False},
                chunking={
                    "top_k": 6,
                    "per_file_limit": 3,
                    "token_budget": 99999,
                    "disclosure": "snippet",
                    "snippet_max_lines": max_lines,
                    "snippet_max_chars": 200,
                },
            ),
        ).plan(
            query="refresh session logic",
            repo="demo",
            root=str(tmp_path),
        )

        method_chunk = next(
            (
                chunk
                for chunk in result["index"]["candidate_chunks"]
                if chunk.get("qualified_name") == "SessionManager.refresh_session"
            ),
            None,
        )
        assert method_chunk is not None

        snippet = str(method_chunk.get("snippet") or "")
        assert snippet
        assert len(snippet.splitlines()) <= max_lines
        assert "def refresh_session" in snippet
