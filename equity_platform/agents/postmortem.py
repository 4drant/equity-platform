from __future__ import annotations

from typing import Any

from equity_platform.agents.base import Agent
from equity_platform.agents.writer import Writer
from equity_platform.data.defeatbeta import DefeatBetaSource
from equity_platform.models.catalysts import Catalyst, CatalystStatus
from equity_platform.store.sqlite import Store


class Postmortem(Agent):
    name = "postmortem"

    def __init__(self, source: DefeatBetaSource, store: Store, llm) -> None:
        super().__init__(llm)
        self.source = source
        self.store = store
        self.writer = Writer(llm)

    def run(self, ticker: str, catalyst: Catalyst, window_days: int = 5) -> Any:
        thesis = self.store.get_thesis(ticker)
        price_move = self._price_move(ticker, catalyst, window_days)
        report = self.writer.postmortem(ticker, catalyst, thesis, price_move)
        self.store.save_report(report)
        catalyst.status = CatalystStatus.RESOLVED
        catalyst.outcome = report.body_md[:500]
        self.store.save_catalyst(catalyst)
        self.store.log_run(self.name, ticker, f"{catalyst.id}: {report.verdict}")
        return report

    def _price_move(self, ticker: str, catalyst: Catalyst, window_days: int) -> float | None:
        if catalyst.expected_date is None or not self.source.available:
            return None
        try:
            prices = self.source.price(ticker, limit=400)
        except Exception:
            return None
        if not prices:
            return None
        target = catalyst.expected_date.isoformat()
        rows = [r for r in prices if str(r.get("report_date", "")) >= target]
        if len(rows) < 2:
            return None
        base_close = float(rows[0]["close"])
        end_close = float(rows[min(window_days, len(rows) - 1)]["close"])
        if base_close == 0:
            return None
        return (end_close - base_close) / base_close
