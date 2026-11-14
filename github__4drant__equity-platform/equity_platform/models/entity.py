from __future__ import annotations

from pydantic import BaseModel, Field

from equity_platform.models.signals import utcnow


class TickerIdentity(BaseModel):
    symbol: str
    name: str = ""
    exchange: str = ""
    sector: str = ""
    industry: str = ""
    market_cap_band: str = ""


class TickerEntity(BaseModel):
    identity: TickerIdentity
    updated_at: object = Field(default_factory=utcnow)
    signal_count: int = 0
    open_catalysts: int = 0
