from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from equity_platform.agents.critic import Critic
from equity_platform.agents.writer import Writer
from equity_platform.data.composite import CompositeSource
from equity_platform.data.factory import build_default_source
from equity_platform.graph.engine import GraphEngine
from equity_platform.llm.client import LLMClient
from equity_platform.loop import ResearchLoop
from equity_platform.models.entity import TickerEntity, TickerIdentity
from equity_platform.models.signals import Classification
from equity_platform.store.sqlite import Store


class Portfolio:
    """Multi-ticker layer: shared loop workers, triage queue, graph synthesis."""

    def __init__(self, store: Store, llm: LLMClient, source: CompositeSource | None = None) -> None:
        self.store = store
        self.llm = llm
        self.source = source or build_default_source()
        self.graph = GraphEngine(store.edges())
        self.writer = Writer(llm)
        self.critic = Critic(llm)

    def add(self, ticker: str) -> TickerEntity:
        ticker = ticker.upper()
        entity = TickerEntity(identity=TickerIdentity(symbol=ticker))
        self.store.save_entity(entity)
        return entity

    def tickers(self) -> list[str]:
        return [e.identity.symbol for e in self.store.entities()]

    def run(self, tickers: list[str] | None = None) -> list[dict[str, Any]]:
        targets = [t.upper() for t in (tickers or self.tickers())]
        results = []
        for ticker in targets:
            loop = ResearchLoop(ticker, self.source, self.store, self.llm, self.graph)
            results.append(loop.run_cycle())
        return results

    def triage_queue(self, limit: int = 20) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        ranked = []
        for signal in self.store.all_signals(limit=1000):
            impact = {"material": 1.0, "relevant": 0.4, "noise": 0.0}[signal.classification.value]
            age_hours = max(0.0, (now - signal.ts).total_seconds() / 3600)
            recency = 1.0 / (1.0 + age_hours / 24.0)
            open_catalysts = self.store.catalysts_for(signal.ticker, status="scheduled")
            catalyst_boost = 1.2 if open_catalysts else 1.0
            score = impact * recency * catalyst_boost * max(0.1, abs(signal.sentiment) + 0.5)
            ranked.append(
                {
                    "signal_id": signal.id,
                    "ticker": signal.ticker,
                    "headline": signal.headline,
                    "classification": signal.classification.value,
                    "sentiment": signal.sentiment,
                    "score": round(score, 4),
                }
            )
        return sorted(ranked, key=lambda r: r["score"], reverse=True)[:limit]

    def propagate_alerts(self, min_abs_sentiment: float = 0.3) -> list[dict[str, Any]]:
        alerts = []
        for signal in self.store.all_signals(limit=300):
            if abs(signal.sentiment) < min_abs_sentiment:
                continue
            impacts = self.graph.propagate(signal.ticker, signal.sentiment)
            for impact in impacts:
                alerts.append(
                    {
                        "origin_signal": signal.id,
                        "origin_ticker": signal.ticker,
                        "headline": signal.headline,
                        **impact,
                    }
                )
        return sorted(alerts, key=lambda a: abs(a["score"]), reverse=True)

    def consistency_flags(self) -> list[str]:
        flags = []
        seen = set()
        for edge in self.graph.edges_for_all():
            pair = edge.key()
            if pair in seen:
                continue
            seen.add(pair)
            if edge.type.value not in ("competitor", "peer_group"):
                continue
            t1, t2 = pair[0], pair[1]
            th1, th2 = self.store.get_thesis(t1), self.store.get_thesis(t2)
            if th1 and th2 and th1.conviction >= 65 and th2.conviction >= 65:
                flags.append(
                    f"High conviction on both {t1} ({th1.conviction}) and {t2} ({th2.conviction})"
                    f" despite {edge.type.value} edge — check for hidden hedging logic."
                )
        return flags

    def weekly_brief(self) -> Any:
        entries = []
        for ticker in self.tickers():
            thesis = self.store.get_thesis(ticker)
            material = self.store.signals_for(ticker, classification=Classification.MATERIAL.value, limit=100)
            open_catalysts = self.store.catalysts_for(ticker, status="scheduled")
            entries.append(
                {
                    "ticker": ticker,
                    "conviction": thesis.conviction if thesis else 50,
                    "material_signals": len(material),
                    "open_catalysts": len(open_catalysts),
                }
            )
        report = self.writer.portfolio_brief(entries, self.consistency_flags(), self.graph.communities())
        return self.critic.verify(report, self.store)
