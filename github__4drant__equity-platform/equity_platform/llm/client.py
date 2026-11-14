from __future__ import annotations

from typing import Protocol

import httpx

from equity_platform.config import Settings, settings


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class LLMClient(Protocol):
    @property
    def available(self) -> bool: ...

    def complete(self, system: str, user: str) -> str: ...


class HeuristicLLM:
    """Offline fallback: agents use their deterministic heuristics."""

    @property
    def available(self) -> bool:
        return False

    def complete(self, system: str, user: str) -> str:
        return ""


class OpenAICompatibleLLM:
    """Any OpenAI-compatible chat completions endpoint (OpenAI, Mistral, vLLM, Ollama...)."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key)

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]


def llm_from_env(cfg: Settings | None = None) -> LLMClient:
    cfg = cfg or settings
    client = OpenAICompatibleLLM(cfg.llm_base_url, cfg.llm_api_key, cfg.llm_model)
    if client.available:
        return client
    return HeuristicLLM()
