from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Classification(str, Enum):
    MATERIAL = "material"
    RELEVANT = "relevant"
    NOISE = "noise"


class Signal(BaseModel):
    id: str
    ticker: str
    ts: datetime = Field(default_factory=utcnow)
    source: str
    url: str = ""
    headline: str = ""
    quote: str = ""
    classification: Classification = Classification.RELEVANT
    confidence: float = 0.5
    facts: list[str] = Field(default_factory=list)
    tickers_mentioned: list[str] = Field(default_factory=list)
    raw_hash: str = ""
    sentiment: float = 0.0
