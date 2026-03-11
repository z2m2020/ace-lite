from __future__ import annotations

from pathlib import Path

from ace_lite.rules import load_rules


def test_load_rules_parses_front_matter_and_orders_by_priority(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".ace-lite" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    (rules_dir / "low.md").write_text(
        "\n".join(
            [
                "---",
                "name: Low Priority",
                "priority: 1",
                "---",
                "low rule",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (rules_dir / "high.md").write_text(
        "\n".join(
            [
                "---",
                "name: High Priority",
                "priority: 9",
                "always_load: true",
                "---",
                "high rule",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = load_rules(root_dir=tmp_path)
    assert payload["count"] == 2
    assert payload["rules"][0]["name"] == "High Priority"
    assert payload["rules"][0]["always_load"] is True
    assert payload["rules"][1]["name"] == "Low Priority"
    assert "high rule" in payload["combined_text"]


def test_load_rules_cache_hit_with_previous_hashes(tmp_path: Path) -> None:
    rules_dir = tmp_path / ".ace-lite" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    rule_path = rules_dir / "demo.md"
    rule_path.write_text("Demo rule\n", encoding="utf-8")

    first = load_rules(root_dir=tmp_path)
    second = load_rules(root_dir=tmp_path, previous_hashes=first["file_hashes"])
    assert second["cache_hit"] is True

    rule_path.write_text("Demo rule updated\n", encoding="utf-8")
    third = load_rules(root_dir=tmp_path, previous_hashes=first["file_hashes"])
    assert third["cache_hit"] is False
