from __future__ import annotations

from equity_platform.agents.base import Agent
from equity_platform.graph.engine import GraphEngine
from equity_platform.models.graph import EdgeType, Relationship
from equity_platform.models.signals import Signal
from equity_platform.store.sqlite import Store

COMPETITOR_SECTORS = {
    "Technology", "Consumer Cyclical", "Communication Services", "Healthcare",
    "Industrials", "Consumer Defensive", "Energy", "Financial Services", "Utilities",
    "Real Estate", "Basic Materials",
}


class Cartographer(Agent):
    name = "cartographer"

    def run(
        self,
        ticker: str,
        signals: list[Signal],
        store: Store,
        graph: GraphEngine,
        sector: str = "",
    ) -> list[Relationship]:
        edges: dict[tuple, Relationship] = {}
        for signal in signals:
            for other in signal.tickers_mentioned:
                if other.upper() == ticker.upper():
                    continue
                key = (ticker.upper(), other.upper(), EdgeType.PEER_GROUP)
                edge = edges.get(key)
                if edge is None:
                    edges[key] = Relationship(
                        source=ticker.upper(),
                        target=other.upper(),
                        type=EdgeType.PEER_GROUP,
                        strength=0.4,
                        evidence_signal_ids=[signal.id],
                    )
                else:
                    edge.strength = min(0.95, edge.strength + 0.1)
                    edge.evidence_signal_ids.append(signal.id)
        if sector in COMPETITOR_SECTORS:
            for (a, b, _), edge in list(edges.items()):
                edges[(a, b, EdgeType.COMPETITOR)] = Relationship(
                    source=a,
                    target=b,
                    type=EdgeType.COMPETITOR,
                    strength=edge.strength,
                    evidence_signal_ids=list(edge.evidence_signal_ids),
                )
        saved = []
        for edge in edges.values():
            store.save_edge(edge)
            graph.add_edge(edge)
            saved.append(edge)
        if saved:
            store.log_run(self.name, ticker, f"discovered {len(saved)} edges")
        return saved
