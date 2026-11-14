from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from equity_platform.models.signals import utcnow


class Stance(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    BASE = "base"


class ThesisLeg(BaseModel):
    stance: Stance
    claim: str
    supporting_signal_ids: list[str] = Field(default_factory=list)


class Assumption(BaseModel):
    id: str
    text: str
    status: str = "active"


class InvalidationTrigger(BaseModel):
    id: str
    description: str
    pattern: str
    status: str = "armed"
    fired_signal_id: str = ""


class Thesis(BaseModel):
    ticker: str
    legs: list[ThesisLeg] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    triggers: list[InvalidationTrigger] = Field(default_factory=list)
    conviction: int = 50
    updated_at: object = Field(default_factory=utcnow)

    def fired_triggers(self) -> list[InvalidationTrigger]:
        return [t for t in self.triggers if t.status == "fired"]
