from __future__ import annotations

from pathlib import Path

from ace_lite.memory import DualChannelMemoryProvider, MemoryRecord, MemoryRecordCompact
from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig


class ErrorProvider:
    last_channel_used = "mcp"

    def search_compact(self, query: str, *, limit: int | None = None):
        raise RuntimeError("mcp down")

    def fetch(self, handles: list[str]):
        raise RuntimeError("mcp down")


class StaticProvider:
    def __init__(self, channel: str, values: list[MemoryRecord]) -> None:
        self.last_channel_used = channel
        self._values = values

    def search_compact(self, query: str, *, limit: int | None = None):
        rows = [
            MemoryRecordCompact(
                handle=f"{self.last_channel_used}:{idx}",
                preview=value.text,
                score=value.score,
                metadata=dict(value.metadata),
                est_tokens=max(1, len(value.text.split())),
                source=self.last_channel_used,
            )
            for idx, value in enumerate(self._values, start=1)
        ]
        if isinstance(limit, int) and limit > 0:
            return rows[:limit]
        return rows

    def fetch(self, handles: list[str]):
        rows: list[MemoryRecord] = []
        for handle in handles:
            if not handle.startswith(f"{self.last_channel_used}:"):
                continue
            try:
                idx = int(handle.split(":", 1)[1]) - 1
            except (ValueError, IndexError):
                continue
            if idx < 0 or idx >= len(self._values):
                continue
            value = self._values[idx]
            rows.append(
                MemoryRecord(
                    text=value.text,
                    score=value.score,
                    metadata=dict(value.metadata),
                    handle=handle,
                    source=self.last_channel_used,
                )
            )
        return rows


def test_orchestrator_reports_memory_fallback_channel(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "skills" / "s.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nA\n",
        encoding="utf-8",
    )

    secondary = StaticProvider("rest", [MemoryRecord(text="fallback memory")])
    memory_provider = DualChannelMemoryProvider(primary=ErrorProvider(), secondary=secondary)

    config = OrchestratorConfig(
        skills={
            "dir": tmp_path / "skills",
        },
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={
            "enabled": False,
        },
    )
    orchestrator = AceOrchestrator(memory_provider=memory_provider, config=config)

    payload = orchestrator.plan(query="implement run", repo="demo", root=str(tmp_path))

    assert payload["memory"]["count"] == 1
    assert payload["memory"]["channel_used"] == "rest"
    assert payload["memory"]["fallback_reason"] == "primary_error:RuntimeError"
    assert payload["index"]["languages_covered"] == ["python"]
