"""Section resolvers for layered CLI config."""

from .memory import resolve_memory_config
from .quality import resolve_quality_config
from .retrieval import resolve_retrieval_and_lsp_config

__all__ = [
    "resolve_memory_config",
    "resolve_quality_config",
    "resolve_retrieval_and_lsp_config",
]
