from __future__ import annotations

from ace_lite.memory.gate import decide_memory_retrieval


def test_memory_gate_skips_empty() -> None:
    decision = decide_memory_retrieval(query="   ")
    assert decision.should_retrieve is False
    assert decision.reason == "empty"


def test_memory_gate_forces_retrieve_for_memory_intent_short() -> None:
    decision = decide_memory_retrieval(query="remember?")
    assert decision.should_retrieve is True
    assert decision.reason == "force"


def test_memory_gate_skips_greeting() -> None:
    decision = decide_memory_retrieval(query="hello")
    assert decision.should_retrieve is False


def test_memory_gate_skips_shell_command() -> None:
    decision = decide_memory_retrieval(query="git status")
    assert decision.should_retrieve is False


def test_memory_gate_skips_short_non_question() -> None:
    decision = decide_memory_retrieval(query="please")
    assert decision.should_retrieve is False


def test_memory_gate_allows_default_long_query() -> None:
    decision = decide_memory_retrieval(query="what did we decide about memory namespace tags?")
    assert decision.should_retrieve is True
