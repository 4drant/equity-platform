from __future__ import annotations

from equity_platform.llm.client import LLMClient, estimate_tokens


class Agent:
    name = "agent"

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm
        self.tokens_used = 0

    def _complete(self, system: str, user: str) -> str:
        if not self.llm.available:
            return ""
        self.tokens_used += estimate_tokens(system) + estimate_tokens(user)
        return self.llm.complete(system, user)
