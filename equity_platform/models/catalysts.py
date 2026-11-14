from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel


class CatalystType(str, Enum):
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    PRODUCT = "product"
    REGULATORY = "regulatory"
    LEGAL = "legal"
    MA = "m_and_a"
    MACRO = "macro"
    OTHER = "other"


class CatalystStatus(str, Enum):
    SCHEDULED = "scheduled"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class Catalyst(BaseModel):
    id: str
    ticker: str
    type: CatalystType
    title: str
    expected_date: date | None = None
    status: CatalystStatus = CatalystStatus.SCHEDULED
    expected_impact: float = 0.0
    resolution: str = ""
    outcome: str = ""
    source_signal_id: str = ""
