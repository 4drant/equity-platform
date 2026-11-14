from equity_platform.agents.critic import Critic
from equity_platform.agents.writer import Writer
from equity_platform.llm.client import HeuristicLLM
from equity_platform.models.signals import Signal
from equity_platform.store.sqlite import Store


def test_digest_contains_citations():
    store = Store()
    signal = Signal(id="sig-abc", ticker="TSLA", source="test", headline="Headline")
    store.save_signal(signal)
    writer = Writer(HeuristicLLM())
    report = writer.daily_digest("TSLA", [signal], [], None)
    assert "[S:sig-abc]" in report.body_md
    verified = Critic(HeuristicLLM()).verify(report, store)
    assert verified.verdict == "pass"


def test_flash_note_cites_signal():
    signal = Signal(id="sig-xyz", ticker="TSLA", source="test", headline="Big event")
    report = Writer(HeuristicLLM()).flash_note("TSLA", signal, peers=["RIVN"])
    assert "[S:sig-xyz]" in report.body_md
    assert "RIVN" in report.body_md
