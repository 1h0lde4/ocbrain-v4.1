"""
core/memory/retrieval/context/token_counter.py — Session 5.6 Retrieval
Context Builder.

TokenCounter is deliberately pluggable: HeuristicTokenCounter (chars/4, the
well-known rough English-text approximation) is the default so budgeting
works with zero new dependencies. A real tokenizer (tiktoken, a model's own
tokenizer) is a drop-in TokenCounter subclass later -- no other code in
this package needs to change when that happens.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class TokenCounter(ABC):
    @abstractmethod
    def count(self, text: str) -> int: ...


class HeuristicTokenCounter(TokenCounter):
    """chars / chars_per_token, rounded up. Not model-accurate -- a
    deliberately simple, dependency-free default. Swap in a real tokenizer
    via the TokenCounter interface when accuracy matters more than zero
    extra dependencies."""

    def __init__(self, chars_per_token: float = 4.0) -> None:
        self.chars_per_token = max(0.1, chars_per_token)

    def count(self, text: str) -> int:
        if not text:
            return 0
        return max(1, int(len(text) / self.chars_per_token + 0.999))
