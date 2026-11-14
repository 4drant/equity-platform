from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EdgeType(str, Enum):
    COMPETITOR = "competitor"
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    PEER_GROUP = "peer_group"
    SHARED_CATALYST = "shared_catalyst"
    CORRELATION = "correlation"


class Relationship(BaseModel):
    source: str
    target: str
    type: EdgeType
    strength: float = 0.5
    evidence_signal_ids: list[str] = Field(default_factory=list)

    def key(self) -> tuple[str, str, EdgeType]:
        a, b = sorted([self.source.upper(), self.target.upper()])
        return (a, b, self.type)
