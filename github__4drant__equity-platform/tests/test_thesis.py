from equity_platform.agents.thesis import ThesisKeeper
from equity_platform.llm.client import HeuristicLLM
from equity_platform.models.signals import Classification, Signal
from equity_platform.store.sqlite import Store


def make_signal(headline: str, sentiment: float = 0.5, cls=Classification.MATERIAL) -> Signal:
    return Signal(
        id=f"sig-{abs(hash(headline)) % 10**10}",
        ticker="TSLA",
        source="news:test",
        headline=headline,
        quote="",
        classification=cls,
        sentiment=sentiment,
    )


def test_bootstrap_and_conviction_update():
    store = Store()
    keeper = ThesisKeeper(HeuristicLLM())
    thesis = keeper.run("TSLA", [make_signal("Company beats earnings estimates", 0.8)], store)
    assert thesis.conviction > 50
    again = keeper.run("TSLA", [make_signal("Company misses and cuts guidance", -0.8)], store)
    assert again.conviction < thesis.conviction


def test_trigger_fires():
    store = Store()
    keeper = ThesisKeeper(HeuristicLLM())
    thesis = keeper.run("TSLA", [make_signal("Company cuts full-year guidance", -0.5)], store)
    fired = thesis.fired_triggers()
    assert fired and fired[0].description == "guidance cut"
    assert fired[0].fired_signal_id


def test_conviction_clamped():
    store = Store()
    keeper = ThesisKeeper(HeuristicLLM())
    thesis = keeper.run("TSLA", [make_signal("Great news", 1.0)] * 1, store)
    assert 0 <= thesis.conviction <= 100
