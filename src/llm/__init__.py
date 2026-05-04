"""LLM adapter interface and no-op stub."""

from abc import ABC, abstractmethod
from typing import Any


class LLMAdapter(ABC):
    @abstractmethod
    def map_term(self, term: str, context: str) -> str: ...

    @abstractmethod
    def explain_drift(self, drift_item: dict[str, Any]) -> str: ...

    @abstractmethod
    def parse_change_intent(self, text: str) -> dict[str, Any]: ...


class NoOpAdapter(LLMAdapter):
    """Default adapter — returns safe pass-through values without any LLM call."""

    def map_term(self, term: str, context: str) -> str:
        return term

    def explain_drift(self, drift_item: dict[str, Any]) -> str:
        return ""

    def parse_change_intent(self, text: str) -> dict[str, Any]:
        return {}


def get_default_adapter() -> LLMAdapter:
    return NoOpAdapter()
