from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ace_lite.utils import normalize_lower_str, normalize_str


@dataclass(frozen=True, slots=True)
class AceLiteMcpConfig:
    default_root: Path
    default_repo: str
    default_skills_dir: Path
    default_languages: str
    config_pack: str
    tokenizer_model: str
    memory_primary: str
    memory_secondary: str
    memory_timeout: float
    memory_limit: int
    plan_timeout_seconds: float
    mcp_base_url: str
    rest_base_url: str
    embedding_enabled: bool
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_index_path: str
    embedding_rerank_pool: int
    embedding_lexical_weight: float
    embedding_semantic_weight: float
    embedding_min_similarity: float
    embedding_fail_open: bool
    ollama_base_url: str
    user_id: str | None
    app: str
    notes_path: Path
    server_name: str = "ACE-Lite MCP Server"

    @classmethod
    def from_env(
        cls,
        *,
        default_root: str | Path | None = None,
        default_skills_dir: str | Path | None = None,
    ) -> AceLiteMcpConfig:
        def _env_str(name: str) -> str:
            return normalize_str(os.getenv(name), default="")

        def _env_bool(name: str, default: bool) -> bool:
            raw = _env_str(name)
            if not raw:
                return bool(default)
            normalized = raw.strip().lower()
            if normalized in {"1", "true", "yes", "y", "on"}:
                return True
            if normalized in {"0", "false", "no", "n", "off"}:
                return False
            return bool(default)

        def _env_int(name: str, default: int) -> int:
            raw = _env_str(name)
            if not raw:
                return int(default)
            try:
                return int(raw.strip())
            except Exception:
                return int(default)

        def _env_float(name: str, default: float) -> float:
            raw = _env_str(name)
            if not raw:
                return float(default)
            try:
                return float(raw.strip())
            except Exception:
                return float(default)

        resolved_user_id = (
            _env_str("ACE_LITE_USER_ID")
            or _env_str("USERNAME")
            or _env_str("USER")
            or None
        )
        root = (
            Path(default_root).expanduser()
            if default_root is not None
            else Path(os.getenv("ACE_LITE_DEFAULT_ROOT", ".")).expanduser()
        ).resolve()
        skills = (
            Path(default_skills_dir).expanduser()
            if default_skills_dir is not None
            else Path(
                os.getenv(
                    "ACE_LITE_DEFAULT_SKILLS_DIR",
                    str(root / "skills"),
                )
            ).expanduser()
        )
        skills = (root / skills).resolve() if not skills.is_absolute() else skills.resolve()

        repo = normalize_str(
            os.getenv("ACE_LITE_DEFAULT_REPO"),
            default=(root.name or "repo"),
        )
        return cls(
            default_root=root,
            default_repo=repo,
            default_skills_dir=skills,
            default_languages=normalize_str(
                os.getenv("ACE_LITE_DEFAULT_LANGUAGES"),
                default="python,typescript,javascript,go,solidity,rust,java,c,cpp,c_sharp,ruby,php,markdown",
            ),
            config_pack=normalize_str(os.getenv("ACE_LITE_CONFIG_PACK"), default=""),
            tokenizer_model=normalize_str(
                os.getenv("ACE_LITE_TOKENIZER_MODEL"),
                default="gpt-4o-mini",
            ),
            memory_primary=normalize_lower_str(
                os.getenv("ACE_LITE_MEMORY_PRIMARY"),
                default="none",
            ),
            memory_secondary=normalize_lower_str(
                os.getenv("ACE_LITE_MEMORY_SECONDARY"),
                default="none",
            ),
            memory_timeout=max(
                0.1,
                _env_float("ACE_LITE_MEMORY_TIMEOUT", 3.0),
            ),
            memory_limit=max(
                1,
                _env_int("ACE_LITE_MEMORY_LIMIT", 8),
            ),
            plan_timeout_seconds=max(
                1.0,
                _env_float("ACE_LITE_PLAN_TIMEOUT_SECONDS", 25.0),
            ),
            mcp_base_url=normalize_str(
                os.getenv("ACE_LITE_MCP_BASE_URL"),
                default="http://localhost:8765",
            ),
            rest_base_url=normalize_str(
                os.getenv("ACE_LITE_REST_BASE_URL"),
                default="http://localhost:8765",
            ),
            embedding_enabled=_env_bool("ACE_LITE_EMBEDDING_ENABLED", False),
            embedding_provider=normalize_lower_str(
                os.getenv("ACE_LITE_EMBEDDING_PROVIDER"),
                default="hash",
            ),
            embedding_model=normalize_str(
                os.getenv("ACE_LITE_EMBEDDING_MODEL"),
                default="hash-v1",
            ),
            embedding_dimension=max(8, _env_int("ACE_LITE_EMBEDDING_DIMENSION", 256)),
            embedding_index_path=normalize_str(
                os.getenv("ACE_LITE_EMBEDDING_INDEX_PATH"),
                default="context-map/embeddings/index.json",
            ),
            embedding_rerank_pool=max(1, _env_int("ACE_LITE_EMBEDDING_RERANK_POOL", 24)),
            embedding_lexical_weight=max(
                0.0, _env_float("ACE_LITE_EMBEDDING_LEXICAL_WEIGHT", 0.7)
            ),
            embedding_semantic_weight=max(
                0.0, _env_float("ACE_LITE_EMBEDDING_SEMANTIC_WEIGHT", 0.3)
            ),
            embedding_min_similarity=_env_float("ACE_LITE_EMBEDDING_MIN_SIMILARITY", 0.0),
            embedding_fail_open=_env_bool("ACE_LITE_EMBEDDING_FAIL_OPEN", True),
            ollama_base_url=normalize_str(
                os.getenv("ACE_LITE_OLLAMA_BASE_URL"),
                default="http://localhost:11434",
            ),
            user_id=resolved_user_id,
            app=normalize_str(os.getenv("ACE_LITE_APP"), default="codex"),
            notes_path=Path(
                normalize_str(
                    os.getenv("ACE_LITE_NOTES_PATH"),
                    default="context-map/memory_notes.jsonl",
                ),
            ).expanduser(),
        )


__all__ = ["AceLiteMcpConfig"]
