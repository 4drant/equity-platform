import uuid

from equity_platform.models.catalysts import Catalyst, CatalystType
from equity_platform.models.graph import EdgeType, Relationship
from equity_platform.models.reports import Report, ReportType
from equity_platform.models.signals import Signal
from equity_platform.store.sqlite import Store


def test_signal_dedupe_by_hash():
    store = Store()
    s = Signal(id="a", ticker="TSLA", source="x", headline="h", raw_hash="hash1")
    assert store.save_signal(s) is True
    dup = Signal(id="b", ticker="TSLA", source="x", headline="h", raw_hash="hash1")
    assert store.save_signal(dup) is False
    assert len(store.signals_for("TSLA")) == 1


def test_thesis_roundtrip():
    store = Store()
    from equity_platform.agents.thesis import ThesisKeeper
    from equity_platform.llm.client import HeuristicLLM

    keeper = ThesisKeeper(HeuristicLLM())
    thesis = keeper.run("TSLA", [], store)
    loaded = store.get_thesis("TSLA")
    assert loaded is not None
    assert loaded.ticker == thesis.ticker
    assert len(loaded.triggers) == len(thesis.triggers)


def test_report_and_edge_roundtrip():
    store = Store()
    report = Report(id="r", tickers=["TSLA"], type=ReportType.FLASH_NOTE, title="t", body_md="b")
    store.save_report(report)
    assert store.reports_for("TSLA")[0].id == "r"
    edge = Relationship(source="TSLA", target="AAPL", type=EdgeType.PEER_GROUP, strength=0.5)
    store.save_edge(edge)
    assert store.edges()[0].target == "AAPL"


def test_catalysts():
    store = Store()
    c = Catalyst(id="c1", ticker="TSLA", type=CatalystType.EARNINGS, title="Q3 earnings")
    store.save_catalyst(c)
    assert store.catalysts_for("TSLA", status="scheduled")[0].id == "c1"


def test_known_tickers():
    store = Store()
    store.save_signal(Signal(id=str(uuid.uuid4()), ticker="TSLA", source="x"))
    assert "TSLA" in store.known_tickers()
