from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from equity_platform.models.signals import utcnow


class ReportType(str, Enum):
    FLASH_NOTE = "flash_note"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_UPDATE = "weekly_update"
    DEEP_DIVE = "deep_dive"
    CATALYST_POSTMORTEM = "catalyst_postmortem"
    SECTOR_BRIEF = "sector_brief"
    PORTFOLIO_BRIEF = "portfolio_brief"


class Report(BaseModel):
    id: str
    tickers: list[str] = Field(default_factory=list)
    type: ReportType
    title: str
    body_md: str
    cited_signal_ids: list[str] = Field(default_factory=list)
    created_at: object = Field(default_factory=utcnow)
    verdict: str = "pending"
    issues: list[str] = Field(default_factory=list)
