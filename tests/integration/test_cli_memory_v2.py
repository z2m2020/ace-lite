from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

import ace_lite.cli as cli_module
from ace_lite.memory import LocalCacheProvider, NullMemoryProvider
from ace_lite.memory_long_term import (
    LongTermMemoryProvider,
    LongTermMemoryStore,
    build_long_term_fact_contract_v1,
)


def _seed_root(root: Path) -> None:
    (root / "skills").mkdir(parents=True, exist_ok=True)


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_plan_accepts_memory_v2_options(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        captured.update(kwargs)
        return NullMemoryProvider()

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", lambda **kwargs: {"ok": True, "memory": kwargs.get("memory_disclosure_mode")})

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--memory-strategy",
            "semantic",
            "--memory-hybrid-limit",
            "11",
            "--no-memory-cache",
            "--memory-cache-path",
            str(tmp_path / "cache" / "m.jsonl"),
            "--memory-cache-ttl-seconds",
            "120",
            "--memory-cache-max-entries",
            "42",
            "--no-memory-timeline",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True

    assert captured["memory_strategy"] == "semantic"
    assert captured["memory_hybrid_limit"] == 11
    assert captured["memory_cache_enabled"] is False
    assert str(captured["memory_cache_path"]).endswith("m.jsonl")
    assert captured["memory_cache_ttl_seconds"] == 120
    assert captured["memory_cache_max_entries"] == 42


def test_cli_plan_resolves_memory_v2_config(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  memory:
    strategy: hybrid
    cache:
      enabled: true
      path: context-map/custom-memory-cache.jsonl
      ttl_seconds: 777
      max_entries: 123
    timeline:
      enabled: false
    hybrid:
      limit: 9
""".strip()
        + "\n",
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        captured.update(kwargs)
        return NullMemoryProvider()

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", lambda **kwargs: {"ok": True, "strategy": kwargs.get("memory_strategy")})

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True

    assert captured["memory_strategy"] == "hybrid"
    assert captured["memory_hybrid_limit"] == 9
    assert captured["memory_cache_enabled"] is True
    assert captured["memory_cache_ttl_seconds"] == 777
    assert captured["memory_cache_max_entries"] == 123
    assert str(captured["memory_cache_path"]).endswith("custom-memory-cache.jsonl")


def test_cli_plan_accepts_memory_namespace_flags(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--memory-container-tag",
            "team-alpha",
            "--memory-auto-tag-mode",
            "repo",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["memory_container_tag"] == "team-alpha"
    assert captured["memory_auto_tag_mode"] == "repo"


def test_cli_plan_reads_memory_namespace_from_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  memory:
    namespace:
      container_tag: repo-team
      auto_tag_mode: user
""".strip()
        + "\n",
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["memory_container_tag"] == "repo-team"
    assert captured["memory_auto_tag_mode"] == "user"


def test_cli_plan_reads_memory_profile_from_config(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  memory:
    profile:
      enabled: true
      path: context-map/profile.json
      top_n: 6
      token_budget: 240
""".strip()
        + "\n",
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["memory_profile_enabled"] is True
    assert str(captured["memory_profile_path"]).endswith("context-map/profile.json")
    assert captured["memory_profile_top_n"] == 6
    assert captured["memory_profile_token_budget"] == 240


def test_cli_plan_reads_memory_expiry_from_config(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  memory:
    profile:
      expiry_enabled: false
      ttl_days: 30
      max_age_days: 180
    notes:
      enabled: true
      expiry_enabled: false
      ttl_days: 15
      max_age_days: 120
""".strip()
        + "\n",
        encoding="utf-8",
    )

    provider_captured: dict[str, Any] = {}
    run_captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        provider_captured.update(kwargs)
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        run_captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert run_captured["memory_profile_expiry_enabled"] is False
    assert run_captured["memory_profile_ttl_days"] == 30
    assert run_captured["memory_profile_max_age_days"] == 180
    assert provider_captured["memory_notes_expiry_enabled"] is False
    assert provider_captured["memory_notes_ttl_days"] == 15
    assert provider_captured["memory_notes_max_age_days"] == 120


def test_cli_plan_reads_memory_capture_from_config(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  memory:
    capture:
      enabled: true
      notes_path: context-map/notes.jsonl
      min_query_length: 12
      keywords: [fix, bug]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["memory_capture_enabled"] is True
    assert str(captured["memory_capture_notes_path"]).endswith("context-map/notes.jsonl")
    assert captured["memory_capture_min_query_length"] == 12
    assert captured["memory_capture_keywords"] == ["fix", "bug"]


def test_cli_plan_reads_memory_long_term_from_config(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  memory:
    long_term:
      enabled: true
      path: context-map/long-term.db
      top_n: 6
      token_budget: 320
      write_enabled: true
      as_of_enabled: false
""".strip()
        + "\n",
        encoding="utf-8",
    )

    provider_captured: dict[str, Any] = {}
    run_captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        provider_captured.update(kwargs)
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        run_captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert provider_captured["memory_long_term_enabled"] is True
    assert str(provider_captured["memory_long_term_path"]).endswith(
        "context-map/long-term.db"
    )
    assert provider_captured["memory_long_term_top_n"] == 6
    assert provider_captured["memory_long_term_token_budget"] == 320
    assert provider_captured["memory_long_term_write_enabled"] is True
    assert provider_captured["memory_long_term_as_of_enabled"] is False
    assert run_captured["memory_long_term_enabled"] is True
    assert str(run_captured["memory_long_term_path"]).endswith(
        "context-map/long-term.db"
    )
    assert run_captured["memory_long_term_top_n"] == 6
    assert run_captured["memory_long_term_token_budget"] == 320
    assert run_captured["memory_long_term_write_enabled"] is True
    assert run_captured["memory_long_term_as_of_enabled"] is False


def test_create_memory_provider_builds_hybrid_cache_wrapper() -> None:
    provider = cli_module.create_memory_provider(
        primary="mcp",
        secondary="rest",
        memory_strategy="hybrid",
        memory_hybrid_limit=10,
        memory_cache_enabled=True,
        memory_cache_path="context-map/test-memory-cache.jsonl",
        memory_cache_ttl_seconds=300,
        memory_cache_max_entries=50,
        mcp_base_url="http://localhost:8765",
        rest_base_url="http://localhost:8765",
        timeout_seconds=0.1,
        user_id=None,
        app="codex",
        limit=5,
    )

    assert isinstance(provider, LocalCacheProvider)
    assert getattr(provider, "strategy", "") == "hybrid"


def test_create_memory_provider_none_channels_returns_null() -> None:
    provider = cli_module.create_memory_provider(
        primary="none",
        secondary="none",
        memory_strategy="semantic",
        memory_hybrid_limit=10,
        memory_cache_enabled=True,
        memory_cache_path="context-map/test-memory-cache.jsonl",
        memory_cache_ttl_seconds=300,
        memory_cache_max_entries=50,
        mcp_base_url="http://localhost:8765",
        rest_base_url="http://localhost:8765",
        timeout_seconds=0.1,
        user_id=None,
        app="codex",
        limit=5,
    )

    assert isinstance(provider, NullMemoryProvider)


def test_create_memory_provider_none_alias_channels_return_null() -> None:
    provider = cli_module.create_memory_provider(
        primary="off",
        secondary="disabled",
        memory_strategy="semantic",
        memory_hybrid_limit=10,
        memory_cache_enabled=True,
        memory_cache_path="context-map/test-memory-cache.jsonl",
        memory_cache_ttl_seconds=300,
        memory_cache_max_entries=50,
        mcp_base_url="http://localhost:8765",
        rest_base_url="http://localhost:8765",
        timeout_seconds=0.1,
        user_id=None,
        app="codex",
        limit=5,
    )

    assert isinstance(provider, NullMemoryProvider)


def test_create_memory_provider_long_term_enabled_uses_local_store(tmp_path: Path) -> None:
    store_path = tmp_path / "context-map" / "long_term_memory.db"
    LongTermMemoryStore(db_path=store_path).upsert_fact(
        build_long_term_fact_contract_v1(
            fact_id="fact-1",
            fact_type="repo_policy",
            subject="runtime.validation.git",
            predicate="fallback_policy",
            object_value="reuse_checkout_or_skip",
            repo="demo",
            namespace="repo/demo",
            as_of="2026-03-19T09:44:00+08:00",
            valid_from="2026-03-19T09:44:00+08:00",
            derived_from_observation_id="obs-1",
        )
    )

    provider = cli_module.create_memory_provider(
        primary="none",
        secondary="none",
        memory_strategy="semantic",
        memory_hybrid_limit=10,
        memory_cache_enabled=False,
        memory_cache_path="context-map/test-memory-cache.jsonl",
        memory_cache_ttl_seconds=300,
        memory_cache_max_entries=50,
        memory_long_term_enabled=True,
        memory_long_term_path=str(store_path),
        memory_long_term_top_n=4,
        mcp_base_url="http://localhost:8765",
        rest_base_url="http://localhost:8765",
        timeout_seconds=0.1,
        user_id=None,
        app="codex",
        limit=5,
    )

    assert isinstance(provider, LongTermMemoryProvider)
    hits = provider.search_compact("fallback policy", container_tag="repo/demo")
    assert len(hits) == 1
    assert hits[0].metadata["memory_kind"] == "fact"


def test_cli_plan_passes_tokenizer_model_from_flag(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--tokenizer-model",
            "gpt-4.1-mini",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["tokenizer_config"] == {"model": "gpt-4.1-mini"}


def test_cli_plan_reads_tokenizer_model_from_config(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  tokenizer:
    model: gpt-4.1-nano
""".strip()
        + "\n",
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["tokenizer_config"] == {"model": "gpt-4.1-nano"}


def test_cli_plan_accepts_failed_test_report_alias(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    report = tmp_path / "reports" / "junit.xml"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("<testsuite />\n", encoding="utf-8")

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--failed-test-report",
            str(report),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["junit_xml"] == str(report)
    assert captured["sbfl_metric"] == "ochiai"


def test_cli_plan_reads_sbfl_metric_from_config(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  sbfl:
    metric: dstar
""".strip()
        + "\n",
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["sbfl_metric"] == "dstar"


def test_cli_plan_reads_failed_test_report_from_config(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    report = tmp_path / "reports" / "failures.xml"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("<testsuite />\n", encoding="utf-8")

    (tmp_path / ".ace-lite.yml").write_text(
        f"""
plan:
  failed_test_report: {report.as_posix()}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["junit_xml"] == report.as_posix()



def test_cli_plan_accepts_trace_export_options(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    trace_path = tmp_path / "context-map" / "traces" / "plan-trace.jsonl"

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--trace-export",
            "--trace-export-path",
            str(trace_path),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["trace_config"] == {
        "export_enabled": True,
        "export_path": str(trace_path),
        "otlp_enabled": False,
        "otlp_endpoint": "",
        "otlp_timeout_seconds": 1.5,
    }


def test_cli_plan_reads_trace_export_from_config(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  trace:
    export_enabled: true
    export_path: context-map/traces/config-trace.jsonl
""".lstrip(),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["trace_config"] == {
        "export_enabled": True,
        "export_path": "context-map/traces/config-trace.jsonl",
        "otlp_enabled": False,
        "otlp_endpoint": "",
        "otlp_timeout_seconds": 1.5,
    }



def test_cli_plan_accepts_trace_otlp_options(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--trace-otlp",
            "--trace-otlp-endpoint",
            "file://context-map/traces/otlp.json",
            "--trace-otlp-timeout-seconds",
            "2.5",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["trace_config"] == {
        "export_enabled": False,
        "export_path": "context-map/traces/stage_spans.jsonl",
        "otlp_enabled": True,
        "otlp_endpoint": "file://context-map/traces/otlp.json",
        "otlp_timeout_seconds": 2.5,
    }


def test_cli_plan_reads_trace_otlp_from_config(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  trace:
    otlp_enabled: true
    otlp_endpoint: file://context-map/traces/trace-otlp.json
    otlp_timeout_seconds: 3.0
""".lstrip(),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    assert captured["trace_config"] == {
        "export_enabled": False,
        "export_path": "context-map/traces/stage_spans.jsonl",
        "otlp_enabled": True,
        "otlp_endpoint": "file://context-map/traces/trace-otlp.json",
        "otlp_timeout_seconds": 3.0,
    }
