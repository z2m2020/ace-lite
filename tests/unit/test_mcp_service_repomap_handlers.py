from __future__ import annotations

import json
from pathlib import Path

from ace_lite.mcp_server.service_repomap_handlers import handle_repomap_build_request


def test_handle_repomap_build_request_writes_outputs_and_summary(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_index(*, root_dir: str, languages: list[str]) -> dict[str, object]:
        captured["root_dir"] = root_dir
        captured["languages"] = languages
        return {"files": {"src/sample.py": {}}}

    def fake_parse_language_csv(language_csv: str) -> list[str]:
        captured["language_csv"] = language_csv
        return [part.strip() for part in language_csv.split(",") if part.strip()]

    def fake_build_repo_map(**kwargs: object) -> dict[str, object]:
        captured["repo_map_kwargs"] = kwargs
        return {
            "ranking_profile": kwargs["ranking_profile"],
            "budget_tokens": kwargs["budget_tokens"],
            "used_tokens": 128,
            "selected_count": 3,
            "markdown": "# Repo Map\n",
            "nodes": ["src/sample.py"],
        }

    def fake_resolve_output_path(
        *,
        root_path: Path,
        output: str | None,
        default: str,
    ) -> Path:
        relative = output if output is not None else default
        return (root_path / relative).resolve()

    result = handle_repomap_build_request(
        root_path=tmp_path,
        language_csv="python,go",
        budget_tokens=400,
        top_k=10,
        ranking_profile=" Graph ",
        output_json="context-map/repomap.test.json",
        output_md="context-map/repomap.test.md",
        tokenizer_model="gpt-4o-mini",
        build_index_fn=fake_build_index,
        parse_language_csv_fn=fake_parse_language_csv,
        build_repo_map_fn=fake_build_repo_map,
        resolve_output_path_fn=fake_resolve_output_path,
    )

    assert result["ok"] is True
    assert result["languages"] == "python,go"
    assert result["ranking_profile"] == "graph"
    assert result["budget_tokens"] == 400
    assert result["used_tokens"] == 128
    assert result["selected_count"] == 3
    assert Path(result["output_json"]).exists()
    assert Path(result["output_md"]).exists()
    assert captured["root_dir"] == str(tmp_path)
    assert captured["languages"] == ["python", "go"]
    assert captured["language_csv"] == "python,go"
    repo_map_kwargs = captured["repo_map_kwargs"]
    assert isinstance(repo_map_kwargs, dict)
    assert repo_map_kwargs["ranking_profile"] == "graph"
    assert repo_map_kwargs["tokenizer_model"] == "gpt-4o-mini"

    json_payload = json.loads(Path(result["output_json"]).read_text(encoding="utf-8"))
    assert "markdown" not in json_payload
    assert json_payload["nodes"] == ["src/sample.py"]
    assert Path(result["output_md"]).read_text(encoding="utf-8") == "# Repo Map\n"


def test_handle_repomap_build_request_uses_default_outputs_and_normalized_fallbacks(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_index(*, root_dir: str, languages: list[str]) -> dict[str, object]:
        captured["root_dir"] = root_dir
        captured["languages"] = languages
        return {"files": {}}

    def fake_parse_language_csv(language_csv: str) -> list[str]:
        captured["language_csv"] = language_csv
        return [language_csv]

    def fake_build_repo_map(**kwargs: object) -> dict[str, object]:
        captured["repo_map_kwargs"] = kwargs
        return {
            "ranking_profile": kwargs["ranking_profile"],
            "budget_tokens": kwargs["budget_tokens"],
            "used_tokens": 0,
            "selected_count": 0,
            "markdown": "",
        }

    def fake_resolve_output_path(
        *,
        root_path: Path,
        output: str | None,
        default: str,
    ) -> Path:
        relative = output if output is not None else default
        return (root_path / relative).resolve()

    result = handle_repomap_build_request(
        root_path=tmp_path,
        language_csv="python",
        budget_tokens=0,
        top_k=0,
        ranking_profile=" ",
        output_json=None,
        output_md=None,
        tokenizer_model="gpt-4o-mini",
        build_index_fn=fake_build_index,
        parse_language_csv_fn=fake_parse_language_csv,
        build_repo_map_fn=fake_build_repo_map,
        resolve_output_path_fn=fake_resolve_output_path,
    )

    assert result["output_json"] == str((tmp_path / "context-map" / "repo_map.json").resolve())
    assert result["output_md"] == str((tmp_path / "context-map" / "repo_map.md").resolve())
    repo_map_kwargs = captured["repo_map_kwargs"]
    assert isinstance(repo_map_kwargs, dict)
    assert repo_map_kwargs["budget_tokens"] == 1
    assert repo_map_kwargs["top_k"] == 1
    assert repo_map_kwargs["ranking_profile"] == "heuristic"
