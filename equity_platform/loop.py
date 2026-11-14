from __future__ import annotations

from datetime import date
from typing import Any

from equity_platform.agents.cartographer import Cartographer
from equity_platform.agents.critic import Critic
from equity_platform.agents.extract import Extractor
from equity_platform.agents.ingest import Ingestor
from equity_platform.agents.sentinel import Sentinel
from equity_platform.agents.thesis import ThesisKeeper
from equity_platform.agents.writer import Writer
from equity_platform.data.defeatbeta import DefeatBetaSource
from equity_platform.graph.engine import GraphEngine
from equity_platform.llm.client import LLMClient
from equity_platform.store.sqlite import Store


class ResearchLoop:
    """The atomic single-stock research loop (spec section 3)."""

    def __init__(
        self,
        ticker: str,
        source: DefeatBetaSource,
        store: Store,
        llm: LLMClient,
        graph: GraphEngine | None = None,
    ) -> None:
        self.ticker = ticker.upper()
        self.source = source
        self.store = store
        self.graph = graph or GraphEngine(store.edges())
        self.ingestor = Ingestor(source, store, llm)
        self.extractor = Extractor(llm, known_tickers=set(store.known_tickers()))
        self.sentinel = Sentinel(llm)
        self.thesis_keeper = ThesisKeeper(llm)
        self.cartographer = Cartographer(llm)
        self.writer = Writer(llm)
        self.critic = Critic(llm)

    def _sync_earnings_calendar(self) -> int:
        if not self.source.available:
            return 0
        try:
            rows = self.source.earnings_calendar(self.ticker)
        except Exception:
            return 0
        created = 0
        known = {
            c.expected_date.isoformat()
            for c in self.store.catalysts_for(self.ticker)
            if c.expected_date
        }
        for row in rows:
            report_date = str(row.get("report_date") or "")
            if not report_date or report_date in known:
                continue
            from datetime import date as _date

            from equity_platform.models.catalysts import Catalyst, CatalystStatus, CatalystType

            try:
                expected = _date.fromisoformat(report_date[:10])
            except ValueError:
                continue
            self.store.save_catalyst(
                Catalyst(
                    id=f"cat-ern-{self.ticker}-{report_date[:10]}",
                    ticker=self.ticker,
                    type=CatalystType.EARNINGS,
                    title=f"Earnings report ({row.get('fiscal_quarter_ending', 'unknown quarter')})",
                    expected_date=expected,
                    status=CatalystStatus.SCHEDULED if expected > date.today() else CatalystStatus.RESOLVED,
                )
            )
            created += 1
        return created

    def run_cycle(self) -> dict[str, Any]:
        summary: dict[str, Any] = {"ticker": self.ticker}
        summary["calendar_catalysts"] = self._sync_earnings_calendar()
        raw = self.ingestor.run(self.ticker)
        summary["raw_items"] = len(raw)
        signals = self.extractor.run(raw)
        stored = 0
        for signal in signals:
            if self.store.save_signal(signal):
                stored += 1
        summary["signals"] = stored
        alerts = self.sentinel.run(self.ticker, signals, self.store)
        summary["alerts"] = alerts
        profile = {}
        if self.source.available:
            try:
                profile = self.source.profile(self.ticker) or {}
            except Exception:
                profile = {}
        thesis = self.thesis_keeper.run(self.ticker, signals, self.store, profile)
        summary["conviction"] = thesis.conviction
        edges = self.cartographer.run(
            self.ticker, signals, self.store, self.graph, sector=str(profile.get("sector", ""))
        )
        summary["edges"] = len(edges)
        recent = self.store.signals_for(self.ticker, limit=25)
        if any(s.classification.value == "material" for s in signals):
            material = next(s for s in signals if s.classification.value == "material")
            report = self.writer.flash_note(self.ticker, material, self.graph.competitor_context(self.ticker))
            report = self.critic.verify(report, self.store)
            summary["flash_note"] = {"id": report.id, "verdict": report.verdict}
        digest = self.writer.daily_digest(
            self.ticker, recent, self.store.catalysts_for(self.ticker), thesis, alerts
        )
        digest = self.critic.verify(digest, self.store)
        summary["digest"] = {"id": digest.id, "verdict": digest.verdict}
        return summary
