from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any

from equity_platform.agents.base import Agent
from equity_platform.config import Settings, settings
from equity_platform.models.catalysts import Catalyst, CatalystStatus, CatalystType
from equity_platform.models.signals import Classification, Signal
from equity_platform.store.sqlite import Store

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june",
         "july", "august", "september", "october", "november", "december"]
    )
}

DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), lambda m: date(int(m[1]), int(m[2]), int(m[3]))),
    (
        re.compile(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})\b",
            re.IGNORECASE,
        ),
        lambda m: date(int(m[3]), MONTHS[m[1].lower()], int(m[2])),
    ),
]

CATALYST_TYPE_PATTERNS = [
    (re.compile(r"\bearnings\b|\bresults\b", re.IGNORECASE), CatalystType.EARNINGS),
    (re.compile(r"\bguidance\b|\bforecast\b|\boutlook\b", re.IGNORECASE), CatalystType.GUIDANCE),
    (re.compile(r"\bfda\b|\bapproval\b|\bclinical\b", re.IGNORECASE), CatalystType.REGULATORY),
    (re.compile(r"\blawsuit\b|\blitigation\b|\bcourt\b", re.IGNORECASE), CatalystType.LEGAL),
    (re.compile(r"\bacquisition\b|\bmerger\b|\btakeover\b", re.IGNORECASE), CatalystType.MA),
    (re.compile(r"\blaunch\b|\bunveil\w*|\brelease\b|\bproduct\b", re.IGNORECASE), CatalystType.PRODUCT),
]


def detect_catalyst_type(text: str) -> CatalystType:
    for pattern, ctype in CATALYST_TYPE_PATTERNS:
        if pattern.search(text):
            return ctype
    return CatalystType.OTHER


def extract_date(text: str) -> date | None:
    for pattern, builder in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return builder(match)
            except ValueError:
                continue
    return None


class Sentinel(Agent):
    name = "sentinel"

    def __init__(self, llm, cfg: Settings | None = None) -> None:
        super().__init__(llm)
        self.cfg = cfg or settings

    def run(self, ticker: str, signals: list[Signal], store: Store) -> list[dict[str, Any]]:
        self._discover_catalysts(ticker, signals, store)
        return self.proximity_alerts(ticker, store)

    def _discover_catalysts(self, ticker: str, signals: list[Signal], store: Store) -> int:
        created = 0
        for signal in signals:
            if signal.classification != Classification.MATERIAL:
                continue
            text = f"{signal.headline} {signal.quote}"
            expected = extract_date(text)
            if expected is None:
                continue
            ctype = detect_catalyst_type(text)
            existing = store.catalysts_for(ticker)
            if any(c.expected_date == expected and c.type == ctype for c in existing):
                continue
            store.save_catalyst(
                Catalyst(
                    id=f"cat-{uuid.uuid4().hex[:10]}",
                    ticker=ticker.upper(),
                    type=ctype,
                    title=signal.headline[:160],
                    expected_date=expected,
                    source_signal_id=signal.id,
                )
            )
            created += 1
        return created

    def proximity_alerts(self, ticker: str, store: Store) -> list[dict[str, Any]]:
        today = datetime.now().date()
        alerts = []
        for catalyst in store.catalysts_for(ticker, status=CatalystStatus.SCHEDULED.value):
            if catalyst.expected_date is None:
                continue
            delta = (catalyst.expected_date - today).days
            for window in self.cfg.proximity_windows_days:
                if delta == window:
                    alerts.append(
                        {
                            "ticker": ticker.upper(),
                            "catalyst_id": catalyst.id,
                            "title": catalyst.title,
                            "type": catalyst.type.value,
                            "expected_date": catalyst.expected_date.isoformat(),
                            "days_until": delta,
                            "window": f"T-{window}" if window else "T-0",
                        }
                    )
                    break
        return alerts
