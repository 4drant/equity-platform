from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from equity_platform.agents.base import Agent
from equity_platform.data.defeatbeta import DefeatBetaSource
from equity_platform.llm.client import LLMClient
from equity_platform.store.sqlite import Store


def item_hash(ticker: str, headline: str) -> str:
    return hashlib.sha256(f"{ticker.upper()}|{headline.strip().lower()}".encode()).hexdigest()


class Ingestor(Agent):
    name = "ingestor"

    def __init__(self, source: DefeatBetaSource, store: Store, llm: LLMClient) -> None:
        super().__init__(llm)
        self.source = source
        self.store = store

    def run(self, ticker: str) -> list[dict[str, Any]]:
        ticker = ticker.upper()
        raw: list[dict[str, Any]] = []
        for item in self.source.news(ticker):
            headline = str(item.get("title") or "").strip()
            if not headline:
                continue
            raw.append(
                {
                    "ticker": ticker,
                    "source": f"news:{item.get('publisher', 'unknown')}",
                    "url": str(item.get("link") or ""),
                    "headline": headline,
                    "quote": "",
                    "published": self._parse_date(item.get("report_date")),
                    "raw_hash": item_hash(ticker, headline),
                }
            )
        for item in self.source.filings(ticker):
            form = str(item.get("form_type") or "filing")
            description = str(item.get("form_type_description") or form)
            headline = f"{form}: {description}" if description != form else form
            raw.append(
                {
                    "ticker": ticker,
                    "source": f"sec:{form}",
                    "url": str(item.get("filing_url") or ""),
                    "headline": headline,
                    "quote": "",
                    "published": self._parse_date(item.get("filing_date")),
                    "raw_hash": item_hash(ticker, headline),
                }
            )
        fresh = []
        for item in raw:
            existing = self.store.conn.execute(
                "SELECT 1 FROM signals WHERE ticker = ? AND raw_hash = ?",
                (item["ticker"], item["raw_hash"]),
            ).fetchone()
            if not existing:
                fresh.append(item)
        self.store.log_run(self.name, ticker, f"ingested {len(fresh)} new items of {len(raw)}")
        return fresh

    @staticmethod
    def _parse_date(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value)
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
