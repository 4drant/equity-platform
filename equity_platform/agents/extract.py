from __future__ import annotations

import json
import re
import uuid
from typing import Any

from equity_platform.agents.base import Agent
from equity_platform.llm.client import LLMClient
from equity_platform.models.signals import Classification, Signal

MATERIAL_PATTERNS = [
    r"\bguidance\b",
    r"\bearnings\b",
    r"\blawsuit\b|\blitigation\b|\bsued\b|\binvestigation\b",
    r"\bfda\b|\bapproval\b",
    r"\bacquisition\b|\bmerger\b|\btakeover\b",
    r"\bdowngrade\b|\bupgrade\b|\binitiat\w+ coverage\b",
    r"\brecall\b",
    r"\bbankruptc\w+",
    r"\bceo\b|\bcfo\b|\bresign\w*|\bappoint\w+",
    r"\bcontract\b|\bpartnership\b",
    r"\bbuyback\b|\bdividend\b",
    r"\bstrike\b",
]

POSITIVE_PATTERNS = [
    r"\bbeats?\b",
    r"\brecord\b",
    r"\bgrowth\b|\bgrew\b",
    r"\bupgrades?\b|\bupgraded\b",
    r"\brais\w+ guidance\b|\braised\b",
    r"\bwins?\b|\bawarded\b",
    r"\bapprov\w+\b",
    r"\bexpands?\b|\bexpansion\b",
    r"\bsurpass\w*\b",
]

NEGATIVE_PATTERNS = [
    r"\bmiss\w*\b",
    r"\bcuts?\b|\blowers?\b",
    r"\blawsuit\b|\blitigation\b|\bsued\b|\binvestigation\b",
    r"\brecalls?\b",
    r"\bdowngrades?\b|\bdowngraded\b",
    r"\blayoffs?\b|\blay off\b",
    r"\bbankruptc\w+",
    r"\bplunge[sd]?\b|\bslumps?\b|\btumbl\w+\b",
    r"\bfalls?\b|\bdrops?\b",
]

TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")

NOISE_TICKERS = {
    "THE", "AND", "FOR", "CEO", "CFO", "CTO", "COO", "IPO", "SEC", "FDA", "EPS", "YOY",
    "Q1", "Q2", "Q3", "Q4", "US", "USA", "EU", "UK", "NYSE", "NASDAQ", "AI", "LLC", "INC",
    "CORP", "ETF", "GDP", "CPI", "FED", "APR", "JAN", "FEB", "MAR", "JUN", "JUL", "AUG",
    "SEP", "OCT", "NOV", "DEC", "IT", "AT", "ON", "IN", "TO", "BY", "AS", "AN", "BE", "IS",
    "VS", "NEW", "GET", "TOP", "BIG", "ALL", "ARE", "WAS", "HAS", "HAD", "NOT", "BUT",
}

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
METRIC_RE = re.compile(
    r"[\$€£]?\d+(?:[.,]\d+)*(?:\s?(?:%|bn|billion|million|bps))?", re.IGNORECASE
)


def classify_heuristic(text: str) -> tuple[Classification, float]:
    lowered = text.lower()
    hits = sum(1 for p in MATERIAL_PATTERNS if re.search(p, lowered))
    if hits >= 2:
        return Classification.MATERIAL, min(0.95, 0.6 + 0.1 * hits)
    if hits == 1:
        return Classification.MATERIAL, 0.65
    if len(text) > 80:
        return Classification.RELEVANT, 0.45
    return Classification.NOISE, 0.3


def sentiment_heuristic(text: str) -> float:
    lowered = text.lower()
    score = 0.0
    score += sum(1.0 for p in POSITIVE_PATTERNS if re.search(p, lowered))
    score -= sum(1.0 for p in NEGATIVE_PATTERNS if re.search(p, lowered))
    return max(-1.0, min(1.0, score / 3.0))


def extract_facts(text: str) -> list[str]:
    facts = []
    for sentence in SENTENCE_SPLIT_RE.split(text):
        if METRIC_RE.search(sentence) and len(sentence) < 400:
            facts.append(sentence.strip())
    return facts[:5]


def co_mentioned_tickers(text: str, known: set[str], exclude: str) -> list[str]:
    candidates = {m for m in TICKER_RE.findall(text) if m not in NOISE_TICKERS}
    return sorted((candidates & {k.upper() for k in known}) - {exclude.upper()})


class Extractor(Agent):
    name = "extractor"

    def __init__(self, llm: LLMClient, known_tickers: set[str] | None = None) -> None:
        super().__init__(llm)
        self.known_tickers = {t.upper() for t in (known_tickers or set())}

    def run(self, raw_items: list[dict[str, Any]]) -> list[Signal]:
        signals = []
        for item in raw_items:
            text = f"{item.get('headline', '')}. {item.get('quote', '')}".strip()
            classification, confidence = self._classify(text)
            if classification == Classification.NOISE:
                continue
            signals.append(
                Signal(
                    id=f"sig-{uuid.uuid4().hex[:12]}",
                    ticker=item["ticker"],
                    source=item.get("source", "unknown"),
                    url=item.get("url", ""),
                    headline=item.get("headline", ""),
                    quote=item.get("quote", ""),
                    classification=classification,
                    confidence=confidence,
                    facts=extract_facts(text),
                    tickers_mentioned=self._mentioned_tickers(item, text),
                    raw_hash=item.get("raw_hash", ""),
                    sentiment=sentiment_heuristic(text),
                )
            )
        return signals

    def _mentioned_tickers(self, item: dict[str, Any], text: str) -> list[str]:
        explicit = {t.upper() for t in item.get("tickers", [])}
        explicit.discard(item["ticker"].upper())
        if explicit:
            return sorted(explicit)
        return co_mentioned_tickers(text, self.known_tickers, item["ticker"])

    def _classify(self, text: str) -> tuple[Classification, float]:
        if self.llm.available:
            result = self._classify_llm(text)
            if result is not None:
                return result
        return classify_heuristic(text)

    def _classify_llm(self, text: str) -> tuple[Classification, float] | None:
        system = (
            "You classify financial news for an equity research system. Respond with ONLY a JSON"
            ' object: {"classification": "material"|"relevant"|"noise", "confidence": 0.0-1.0}.'
            " Material means it could change an investment thesis."
        )
        try:
            raw = self._complete(system, text[:4000])
            cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(cleaned)
            return Classification(data["classification"]), float(data.get("confidence", 0.5))
        except Exception:
            return None
