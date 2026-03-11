from __future__ import annotations

from ace_lite.signal_extractor import SignalExtractor


def test_signal_extractor_triggers_on_keyword_and_min_length() -> None:
    extractor = SignalExtractor(keywords=["fix", "bug"], min_query_length=8)

    result = extractor.extract("Need to fix login bug in gateway")

    assert result.triggered is True
    assert result.matched_keywords == ("fix", "bug")
    assert result.reason == "keyword_match"


def test_signal_extractor_rejects_short_query() -> None:
    extractor = SignalExtractor(keywords=["fix"], min_query_length=20)

    result = extractor.extract("fix bug")

    assert result.triggered is False
    assert result.matched_keywords == ()
    assert result.reason == "below_min_length"
