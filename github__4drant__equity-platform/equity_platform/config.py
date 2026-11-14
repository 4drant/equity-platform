from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    db_path: str = field(default_factory=lambda: os.environ.get("EQUITY_DB_PATH", "equity.db"))
    llm_base_url: str = field(default_factory=lambda: os.environ.get("EQUITY_LLM_BASE_URL", ""))
    llm_api_key: str = field(default_factory=lambda: os.environ.get("EQUITY_LLM_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.environ.get("EQUITY_LLM_MODEL", "gpt-4o-mini"))
    daily_token_budget: int = field(
        default_factory=lambda: int(os.environ.get("EQUITY_DAILY_TOKEN_BUDGET", "200000"))
    )
    proximity_windows_days: tuple[int, ...] = (14, 7, 1, 0)
    flash_note_max_minutes: int = 15
    propagation_depth: int = 2
    propagation_decay: float = 0.5
    watchlist: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            t.strip().upper()
            for t in os.environ.get("EQUITY_WATCHLIST", "").split(",")
            if t.strip()
        )
    )


settings = Settings()
