from datetime import datetime, timedelta, timezone

from equity_platform.llm.client import HeuristicLLM
from equity_platform.models.signals import Classification, Signal
from equity_platform.portfolio import Portfolio
from equity_platform.store.sqlite import Store


def make_portfolio() -> Portfolio:
    return Portfolio(Store(), HeuristicLLM())


def seed(store: Store, ticker: str, headline: str, cls: Classification, age_hours: float) -> Signal:
    signal = Signal(
        id=f"sig-{abs(hash(headline)) % 10**10}",
        ticker=ticker,
        source="test",
        headline=headline,
        classification=cls,
        sentiment=0.5,
        ts=datetime.now(timezone.utc) - timedelta(hours=age_hours),
    )
    store.save_signal(signal)
    return signal


def test_triage_ranks_material_recent_first():
    pf = make_portfolio()
    seed(pf.store, "TSLA", "Old relevant item", Classification.RELEVANT, age_hours=100)
    seed(pf.store, "AAPL", "Fresh material item", Classification.MATERIAL, age_hours=1)
    queue = pf.triage_queue()
    assert queue[0]["ticker"] == "AAPL"


def test_add_and_tickers():
    pf = make_portfolio()
    pf.add("tsla")
    assert pf.tickers() == ["TSLA"]


def test_consistency_flags_on_competitor_edges():
    from equity_platform.agents.thesis import ThesisKeeper
    from equity_platform.models.graph import EdgeType, Relationship

    pf = make_portfolio()
    pf.add("TSLA")
    pf.add("RIVN")
    keeper = ThesisKeeper(HeuristicLLM())
    thesis1 = keeper.run("TSLA", [], pf.store)
    thesis1.conviction = 80
    pf.store.save_thesis(thesis1)
    thesis2 = keeper.run("RIVN", [], pf.store)
    thesis2.conviction = 80
    pf.store.save_thesis(thesis2)
    pf.graph.add_edge(Relationship(source="TSLA", target="RIVN", type=EdgeType.COMPETITOR, strength=0.9))
    flags = pf.consistency_flags()
    assert any("TSLA" in f and "RIVN" in f for f in flags)


def test_weekly_brief_runs():
    pf = make_portfolio()
    pf.add("TSLA")
    seed(pf.store, "TSLA", "Material event", Classification.MATERIAL, age_hours=2)
    report = pf.weekly_brief()
    assert report.verdict in ("pass", "fail")
    assert "TSLA" in report.body_md
