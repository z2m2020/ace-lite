from __future__ import annotations

from pathlib import Path

import pytest

import ace_lite.index_stage.docs_channel as docs_channel
from ace_lite.index_stage.docs_channel import collect_docs_signals
from ace_lite.sqlite_mirror import DocsMirrorResult


def test_collect_docs_signals_extracts_evidence_and_code_hints(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(
        """
# Auth Architecture
The architecture focuses on `src/core/auth.py` and module `src.core.auth`.

## Retry Mechanism
The function `refresh_session` validates retry backoff behavior.
""".strip()
        + "\n",
        encoding="utf-8",
    )

    first = collect_docs_signals(
        root=tmp_path,
        query="how does retry mechanism work in auth architecture",
        terms=["retry", "auth", "mechanism"],
        enabled=True,
        intent_weight=1.2,
        max_sections=6,
    )
    second = collect_docs_signals(
        root=tmp_path,
        query="how does retry mechanism work in auth architecture",
        terms=["retry", "auth", "mechanism"],
        enabled=True,
        intent_weight=1.2,
        max_sections=6,
    )

    assert first["enabled"] is True
    assert first["reason"] == "ok"
    assert first["backend"] in {"mirror_fts5_bm25", "fts5_bm25", "python_bm25"}
    assert first["cache_layer"] == "none"
    assert first["cache_store_written"] is True
    assert str(first["cache_path"]).endswith("context-map/docs_sections_cache.json")
    assert first["repo_glossary_size"] > 0
    assert isinstance(first["repo_glossary_sample"], list)
    assert first["repo_glossary_cache_hit"] is False
    assert first["repo_glossary_cache_layer"] == "none"
    assert str(first["repo_glossary_cache_path"]).endswith("context-map/docs_repo_glossary_cache.json")
    assert first["section_count"] >= 1
    assert first["evidence"]
    first_evidence = first["evidence"][0]
    snippet = str(first_evidence.get("snippet") or "")
    assert str(first_evidence.get("doc_title") or "") == "Auth Architecture"
    glossary_terms = first_evidence.get("glossary_terms")
    assert isinstance(glossary_terms, list)
    assert "retry" in glossary_terms
    assert "auth" in glossary_terms
    assert "terms:" in snippet
    assert str(first_evidence.get("path") or "") in snippet
    assert str(first_evidence.get("heading_path") or "") in snippet
    assert len(snippet) <= 240
    hints = first["hints"]
    assert "src/core/auth.py" in hints["paths"]
    assert "src.core.auth" in hints["modules"]
    assert "refresh_session" in hints["symbols"]
    explainability = first["explainability"]
    assert explainability["backend"] == first["backend"]
    assert explainability["evidence_sources"][0]["path"] == first_evidence["path"]
    assert any(item["value"] == "auth" for item in explainability["top_matched_terms"])
    assert any(item["value"] == "retry" for item in explainability["top_matched_terms"])
    assert any(note.startswith("backend:") for note in explainability["selection_notes"])
    assert any(
        note == "hinted_path:src/core/auth.py"
        for note in explainability["selection_notes"]
    )
    assert second["cache_hit"] is True
    assert second["cache_layer"] == "memory"
    assert second["cache_store_written"] is False
    assert second["repo_glossary_cache_hit"] is True
    assert second["repo_glossary_cache_layer"] == "memory"


def test_collect_docs_signals_drops_doc_filenames_from_module_hints(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(
        """
# Engine Architecture

 Architecture overview.
 See docs/README.md and pyproject.toml for packaging notes.
 Generated caches live at context-map/index.json.
 The implementation lives in module `ace_lite.index_cache`.
""".strip()
        + "\n",
        encoding="utf-8",
    )

    payload = collect_docs_signals(
        root=tmp_path,
        query="architecture overview",
        terms=["architecture", "overview"],
        enabled=True,
        intent_weight=1.0,
        max_sections=6,
    )

    hints = payload["hints"]
    assert "ace_lite.index_cache" in hints["modules"]
    assert "README.md" not in hints["modules"]
    assert "pyproject.toml" not in hints["modules"]
    assert "index.json" not in hints["modules"]


def test_collect_docs_signals_handles_missing_docs(tmp_path: Path) -> None:
    payload = collect_docs_signals(
        root=tmp_path,
        query="architecture overview",
        terms=["architecture"],
        enabled=True,
        intent_weight=1.0,
    )

    assert payload["enabled"] is True
    assert payload["reason"] == "no_docs_sections"
    assert payload["backend"] == "none"
    assert payload["section_count"] == 0
    assert payload["hints"]["paths"] == []
    assert payload["explainability"]["reason"] == "no_docs_sections"
    assert payload["explainability"]["backend"] == "none"
    assert "reason:no_docs_sections" in payload["explainability"]["selection_notes"]


def test_collect_docs_signals_can_hit_disk_cache_after_memory_reset(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(
        "# Auth Architecture\nsrc/core/auth.py\n",
        encoding="utf-8",
    )

    first = collect_docs_signals(
        root=tmp_path,
        query="auth architecture",
        terms=["auth", "architecture"],
        enabled=True,
        intent_weight=1.0,
    )
    docs_channel._SECTION_CACHE.clear()
    docs_channel._REPO_GLOSSARY_CACHE.clear()
    second = collect_docs_signals(
        root=tmp_path,
        query="auth architecture",
        terms=["auth", "architecture"],
        enabled=True,
        intent_weight=1.0,
    )

    assert first["cache_hit"] is False
    assert first["cache_store_written"] is True
    assert second["cache_hit"] is True
    assert second["cache_layer"] == "disk"
    assert second["cache_store_written"] is False
    assert second["repo_glossary_cache_hit"] is True
    assert second["repo_glossary_cache_layer"] == "disk"


def test_collect_docs_signals_uses_fts_backend_when_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(
        "# System Architecture\n`src/core/auth.py`\n",
        encoding="utf-8",
    )

    def _fake_rank_sections_fts5(
        *,
        sections: list[dict[str, object]],
        query_tokens: list[str],
        intent_weight: float,
    ) -> list[dict[str, object]]:
        row = dict(sections[0])
        row["score"] = 2.0
        row["matched_terms"] = list(query_tokens[:1]) or ["architecture"]
        return [row]

    monkeypatch.setattr(docs_channel, "_sqlite_supports_fts5", lambda: True)
    monkeypatch.setattr(
        docs_channel,
        "ensure_docs_fts_mirror",
        lambda **_: DocsMirrorResult(
            enabled=False,
            reason="disabled_for_test",
            path=str(tmp_path / "context-map" / "index.db"),
            cache_hit=False,
            rebuilt=False,
            fts5_available=True,
            docs_fingerprint="",
            section_count=0,
            elapsed_ms=0.0,
            warning=None,
        ),
    )
    monkeypatch.setattr(docs_channel, "_rank_sections_fts5", _fake_rank_sections_fts5)

    payload = collect_docs_signals(
        root=tmp_path,
        query="architecture auth",
        terms=["architecture", "auth"],
        enabled=True,
        intent_weight=1.0,
    )

    assert payload["backend"] == "fts5_bm25"
    assert payload["backend_fallback_reason"] == ""
    assert payload["evidence"]


def test_collect_docs_signals_prefers_mirror_backend_when_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(
        "# System Architecture\nsrc/core/auth.py\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(docs_channel, "_sqlite_supports_fts5", lambda: True)
    monkeypatch.setattr(
        docs_channel,
        "ensure_docs_fts_mirror",
        lambda **_: DocsMirrorResult(
            enabled=True,
            reason="cache_hit",
            path=str(tmp_path / "context-map" / "index.db"),
            cache_hit=True,
            rebuilt=False,
            fts5_available=True,
            docs_fingerprint="test",
            section_count=1,
            elapsed_ms=0.0,
            warning=None,
        ),
    )
    monkeypatch.setattr(docs_channel, "query_docs_fts", lambda **_: [(1, -10.0)])

    payload = collect_docs_signals(
        root=tmp_path,
        query="system architecture",
        terms=["architecture"],
        enabled=True,
        intent_weight=1.0,
    )

    assert payload["backend"] == "mirror_fts5_bm25"
    assert payload["mirror"]["enabled"] is True
    assert payload["evidence"]


def test_collect_docs_signals_falls_back_to_in_memory_fts_when_mirror_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(
        "# Auth Architecture\nretry mechanism in src/core/auth.py\n",
        encoding="utf-8",
    )

    def _fake_rank_sections_fts5(
        *,
        sections: list[dict[str, object]],
        query_tokens: list[str],
        intent_weight: float,
    ) -> list[dict[str, object]]:
        row = dict(sections[0])
        row["score"] = 1.0
        row["matched_terms"] = list(query_tokens[:1]) or ["retry"]
        return [row]

    monkeypatch.setattr(docs_channel, "_sqlite_supports_fts5", lambda: True)
    monkeypatch.setattr(
        docs_channel,
        "ensure_docs_fts_mirror",
        lambda **_: DocsMirrorResult(
            enabled=True,
            reason="cache_hit",
            path=str(tmp_path / "context-map" / "index.db"),
            cache_hit=True,
            rebuilt=False,
            fts5_available=True,
            docs_fingerprint="test",
            section_count=1,
            elapsed_ms=0.0,
            warning=None,
        ),
    )
    monkeypatch.setattr(docs_channel, "query_docs_fts", lambda **_: [])
    monkeypatch.setattr(docs_channel, "_rank_sections_fts5", _fake_rank_sections_fts5)

    payload = collect_docs_signals(
        root=tmp_path,
        query="retry mechanism",
        terms=["retry"],
        enabled=True,
        intent_weight=1.0,
    )

    assert payload["backend"] == "fts5_bm25"
    assert payload["evidence"]


def test_collect_docs_signals_falls_back_when_fts_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(
        "# Auth Architecture\nretry mechanism in src/core/auth.py\n",
        encoding="utf-8",
    )

    def _raise_fts_error(
        *,
        sections: list[dict[str, object]],
        query_tokens: list[str],
        intent_weight: float,
    ) -> list[dict[str, object]]:
        _ = (sections, query_tokens, intent_weight)
        raise RuntimeError("fts down")

    monkeypatch.setattr(docs_channel, "_sqlite_supports_fts5", lambda: True)
    monkeypatch.setattr(
        docs_channel,
        "ensure_docs_fts_mirror",
        lambda **_: DocsMirrorResult(
            enabled=False,
            reason="disabled_for_test",
            path=str(tmp_path / "context-map" / "index.db"),
            cache_hit=False,
            rebuilt=False,
            fts5_available=True,
            docs_fingerprint="",
            section_count=0,
            elapsed_ms=0.0,
            warning=None,
        ),
    )
    monkeypatch.setattr(docs_channel, "_rank_sections_fts5", _raise_fts_error)

    payload = collect_docs_signals(
        root=tmp_path,
        query="how retry works",
        terms=["retry", "works"],
        enabled=True,
        intent_weight=1.0,
    )

    assert payload["backend"] == "python_bm25"
    assert payload["backend_fallback_reason"] == "fts5_error:RuntimeError"
    assert payload["evidence"]
    assert payload["explainability"]["fallback_reason"] == "fts5_error:RuntimeError"
    assert "fallback:fts5_error:RuntimeError" in payload["explainability"]["selection_notes"]


def test_collect_docs_signals_marks_unavailable_fts_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(
        "# System Architecture\nsrc/core/auth.py\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(docs_channel, "_sqlite_supports_fts5", lambda: False)

    payload = collect_docs_signals(
        root=tmp_path,
        query="system architecture",
        terms=["architecture"],
        enabled=True,
        intent_weight=1.0,
    )

    assert payload["backend"] == "python_bm25"
    assert payload["backend_fallback_reason"] == "fts5_unavailable"
