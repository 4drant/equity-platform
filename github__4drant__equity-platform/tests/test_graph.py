from equity_platform.graph.engine import GraphEngine
from equity_platform.models.graph import EdgeType, Relationship


def build() -> GraphEngine:
    engine = GraphEngine()
    engine.add_edge(Relationship(source="TSLA", target="RIVN", type=EdgeType.COMPETITOR, strength=0.8))
    engine.add_edge(Relationship(source="RIVN", target="LCID", type=EdgeType.COMPETITOR, strength=0.7))
    engine.add_edge(Relationship(source="TSLA", target="PANW", type=EdgeType.PEER_GROUP, strength=0.4))
    return engine


def test_propagation_ranks_and_decays():
    engine = build()
    impacts = engine.propagate("TSLA", impact=-1.0, max_depth=2, decay=0.5)
    by_ticker = {i["ticker"]: i for i in impacts}
    assert "RIVN" in by_ticker
    assert by_ticker["RIVN"]["score"] < 0
    assert abs(by_ticker["RIVN"]["score"]) > abs(by_ticker.get("LCID", {"score": 0})["score"])
    assert by_ticker["RIVN"]["path"] == ["TSLA", "RIVN"]


def test_propagation_respects_depth():
    engine = build()
    impacts = engine.propagate("TSLA", impact=-1.0, max_depth=1)
    assert all(i["ticker"] != "LCID" for i in impacts)


def test_communities():
    engine = build()
    clusters = engine.communities(min_strength=0.3)
    assert any({"TSLA", "RIVN", "LCID"} <= cluster for cluster in clusters)


def test_competitor_context():
    engine = build()
    peers = engine.competitor_context("TSLA")
    assert "RIVN" in peers
    assert "PANW" in peers
