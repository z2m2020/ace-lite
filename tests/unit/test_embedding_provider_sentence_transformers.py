from __future__ import annotations

from ace_lite.cli_app.params import _to_embedding_provider
from ace_lite.config_models import EmbeddingsConfig


def test_click_coercion_accepts_sentence_transformers_provider() -> None:
    assert _to_embedding_provider("sentence_transformers") == "sentence_transformers"


def test_config_models_accepts_sentence_transformers_provider() -> None:
    config = EmbeddingsConfig(provider="sentence_transformers")
    assert config.provider == "sentence_transformers"
