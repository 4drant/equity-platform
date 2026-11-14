from equity_platform.agents.extract import (
    Extractor,
    classify_heuristic,
    co_mentioned_tickers,
    extract_facts,
    sentiment_heuristic,
)
from equity_platform.llm.client import HeuristicLLM
from equity_platform.models.signals import Classification


def test_material_classification():
    text = "The company cuts full-year guidance and reported earnings missed estimates."
    cls, conf = classify_heuristic(text)
    assert cls == Classification.MATERIAL
    assert conf > 0.6


def test_noise_classification():
    cls, _ = classify_heuristic("Stocks ticked up slightly today.")
    assert cls == Classification.NOISE


def test_sentiment_signs():
    assert sentiment_heuristic("Company beats estimates and raises guidance") > 0
    assert sentiment_heuristic("Company misses, faces lawsuit and recalls product") < 0


def test_extract_facts_numbers():
    facts = extract_facts("Revenue grew 12% to $25.7 billion. The weather was nice.")
    assert any("12%" in f for f in facts)
    assert all("weather" not in f for f in facts)


def test_co_mention_filtering():
    known = {"AAPL", "MSFT", "CEO"}
    assert co_mentioned_tickers("AAPL vs MSFT and the CEO", known, "AAPL") == ["MSFT"]


def test_extractor_skips_noise():
    extractor = Extractor(HeuristicLLM(), known_tickers={"AAPL"})
    signals = extractor.run(
        [
            {
                "ticker": "TSLA",
                "source": "news:test",
                "url": "",
                "headline": "Meh",
                "quote": "",
                "raw_hash": "h1",
            }
        ]
    )
    assert signals == []


def test_extractor_co_mention():
    extractor = Extractor(HeuristicLLM(), known_tickers={"AAPL"})
    signals = extractor.run(
        [
            {
                "ticker": "TSLA",
                "source": "news:test",
                "url": "",
                "headline": "TSLA earnings beat; analysts compare to AAPL supply chain",
                "quote": "Margins grew 5%.",
                "raw_hash": "h2",
            }
        ]
    )
    assert len(signals) == 1
    assert signals[0].tickers_mentioned == ["AAPL"]
    assert signals[0].classification == Classification.MATERIAL
