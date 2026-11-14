import uuid

from equity_platform.agents.critic import Critic
from equity_platform.llm.client import HeuristicLLM
from equity_platform.models.reports import Report, ReportType
from equity_platform.models.signals import Signal
from equity_platform.store.sqlite import Store


def store_with_signal() -> tuple[Store, Signal]:
    store = Store()
    signal = Signal(id=f"sig-{uuid.uuid4().hex[:10]}", ticker="TSLA", source="test", headline="h")
    store.save_signal(signal)
    return store, signal


def test_pass_with_valid_citations():
    store, signal = store_with_signal()
    report = Report(
        id="r1",
        tickers=["TSLA"],
        type=ReportType.DAILY_DIGEST,
        title="t",
        body_md=f"Claim here [S:{signal.id}]",
        cited_signal_ids=[signal.id],
    )
    verified = Critic(HeuristicLLM()).verify(report, store)
    assert verified.verdict == "pass"
    assert verified.issues == []


def test_fail_on_unresolved_citation():
    store, _ = store_with_signal()
    report = Report(
        id="r2",
        tickers=["TSLA"],
        type=ReportType.DAILY_DIGEST,
        title="t",
        body_md="Claim [S:sig-doesnotexist]",
        cited_signal_ids=["sig-doesnotexist"],
    )
    verified = Critic(HeuristicLLM()).verify(report, store)
    assert verified.verdict == "fail"
    assert verified.issues


def test_fail_on_inline_citation_missing_from_list():
    store, signal = store_with_signal()
    report = Report(
        id="r3",
        tickers=["TSLA"],
        type=ReportType.DAILY_DIGEST,
        title="t",
        body_md=f"Claim [S:{signal.id}]",
        cited_signal_ids=[],
    )
    verified = Critic(HeuristicLLM()).verify(report, store)
    assert verified.verdict == "fail"
