from __future__ import annotations

import re
import uuid
from typing import Any

from equity_platform.agents.base import Agent
from equity_platform.models.thesis import (
    Assumption,
    InvalidationTrigger,
    Stance,
    Thesis,
    ThesisLeg,
)
from equity_platform.models.signals import Signal
from equity_platform.store.sqlite import Store

DEFAULT_TRIGGERS = [
    ("guidance cut", r"\b(cuts?|lowers?)\s+(full[- ]year\s+)?guidance\b"),
    ("sec investigation", r"\b(sec\s+investigation|subpoena)\b"),
    ("cfo departure", r"\bcfo\s+(resigns?|departs?|steps down)\b"),
    ("going concern", r"\bgoing concern\b"),
    ("major recall", r"\brecalls?\b"),
]


class ThesisKeeper(Agent):
    name = "thesis_keeper"

    def bootstrap(self, ticker: str, profile: dict[str, Any] | None = None) -> Thesis:
        profile = profile or {}
        name = profile.get("longName") or profile.get("shortName") or ticker.upper()
        sector = profile.get("sector", "")
        return Thesis(
            ticker=ticker.upper(),
            legs=[
                ThesisLeg(
                    stance=Stance.BULL,
                    claim=f"{name} benefits from durable demand in {sector or 'its end market'} and operational leverage.",
                ),
                ThesisLeg(
                    stance=Stance.BEAR,
                    claim=f"{name} faces competitive pressure and multiple compression if growth decelerates.",
                ),
                ThesisLeg(
                    stance=Stance.BASE,
                    claim=f"{name} compounds roughly in line with its sector; conviction tracks quarterly execution.",
                ),
            ],
            assumptions=[
                Assumption(id=f"asm-{uuid.uuid4().hex[:8]}", text="Revenue growth stays positive YoY"),
                Assumption(id=f"asm-{uuid.uuid4().hex[:8]}", text="Margins do not compress more than 200bps YoY"),
            ],
            triggers=[
                InvalidationTrigger(
                    id=f"trg-{uuid.uuid4().hex[:8]}", description=desc, pattern=pattern
                )
                for desc, pattern in DEFAULT_TRIGGERS
            ],
            conviction=50,
        )

    def run(
        self,
        ticker: str,
        signals: list[Signal],
        store: Store,
        profile: dict[str, Any] | None = None,
    ) -> Thesis:
        is_new = store.get_thesis(ticker) is None
        thesis = store.get_thesis(ticker) or self.bootstrap(ticker, profile)
        material = [s for s in signals if s.classification.value == "material"]
        for trigger in thesis.triggers:
            if trigger.status != "armed":
                continue
            for signal in material:
                text = f"{signal.headline} {signal.quote}"
                if re.search(trigger.pattern, text, re.IGNORECASE):
                    trigger.status = "fired"
                    trigger.fired_signal_id = signal.id
                    break
        if material:
            sentiment_delta = sum(s.sentiment for s in material) * 5
            fired_penalty = len(thesis.fired_triggers()) * -10
            if is_new:
                thesis.conviction = int(max(0, min(100, 50 + sentiment_delta + fired_penalty)))
            else:
                thesis.conviction = int(
                    max(0, min(100, thesis.conviction + sentiment_delta + fired_penalty))
                )
        if signals:
            thesis.updated_at = signals[-1].ts
        store.save_thesis(thesis)
        store.log_run(
            self.name,
            ticker,
            f"conviction={thesis.conviction} triggers_fired={len(thesis.fired_triggers())}",
        )
        return thesis
