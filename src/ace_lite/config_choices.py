from __future__ import annotations

REMOTE_SLOT_POLICY_CHOICES: tuple[str, ...] = ("strict", "warn", "off")
RETRIEVAL_POLICY_CHOICES: tuple[str, ...] = (
    "auto",
    "bugfix_test",
    "doc_intent",
    "feature",
    "refactor",
    "general",
)
ADAPTIVE_ROUTER_MODE_CHOICES: tuple[str, ...] = ("observe", "shadow", "enforce")
CHUNK_GUARD_MODE_CHOICES: tuple[str, ...] = ("off", "report_only", "enforce")
TOPOLOGICAL_SHIELD_MODE_CHOICES: tuple[str, ...] = (
    "off",
    "report_only",
    "enforce",
)
MEMORY_AUTO_TAG_MODE_CHOICES: tuple[str, ...] = ("repo", "user", "global")
MEMORY_NOTES_MODE_CHOICES: tuple[str, ...] = (
    "supplement",
    "prefer_local",
    "local_only",
)
MEMORY_TIMEZONE_MODE_CHOICES: tuple[str, ...] = ("utc", "local", "explicit")
MEMORY_GATE_MODE_CHOICES: tuple[str, ...] = ("auto", "always", "never")
EMBEDDING_PROVIDER_CHOICES: tuple[str, ...] = (
    "hash",
    "hash_cross",
    "hash_colbert",
    "bge_m3",
    "bge_reranker",
    "sentence_transformers",
    "ollama",
)

__all__ = [
    "ADAPTIVE_ROUTER_MODE_CHOICES",
    "CHUNK_GUARD_MODE_CHOICES",
    "EMBEDDING_PROVIDER_CHOICES",
    "MEMORY_AUTO_TAG_MODE_CHOICES",
    "MEMORY_GATE_MODE_CHOICES",
    "MEMORY_NOTES_MODE_CHOICES",
    "MEMORY_TIMEZONE_MODE_CHOICES",
    "REMOTE_SLOT_POLICY_CHOICES",
    "RETRIEVAL_POLICY_CHOICES",
    "TOPOLOGICAL_SHIELD_MODE_CHOICES",
]
