from __future__ import annotations

import sys
import types

import pytest

from equity_platform.data.composite import CompositeSource
from equity_platform.data.factory import build_default_source
from equity_platform.data.yfinance import YFinanceSource


class FakeSource:
    def __init__(self, **overrides):
        self._overrides = overrides
        self.available = True
        self.calls: list[str] = []

    def _result(self, method, default):
        self.calls.append(method)
        return self._overrides.get(method, default)

    def news(self, symbol, limit=20):
        return self._result("news", [])

    def filings(self, symbol, limit=10):
        return self._result("filings", [])

    def profile(self, symbol):
        return self._result("profile", {})

    def price(self, symbol, limit=30):
        return self._result("price", [])

    def earnings_calendar(self, symbol):
        return self._result("earnings_calendar", [])

    def transcripts_catalog(self, symbol):
        return self._result("transcripts_catalog", [])

    def transcript(self, symbol, fiscal_year, fiscal_quarter):
        return self._result("transcript", [])

    def quarterly_income_statement(self, symbol):
        return self._result("quarterly_income_statement", [])

    def quarterly_balance_sheet(self, symbol):
        return self._result("quarterly_balance_sheet", [])

    def quarterly_cash_flow(self, symbol):
        return self._result("quarterly_cash_flow", [])


class BrokenSource:
    available = False
    last_error = ""

    def news(self, symbol, limit=20):
        raise RuntimeError("boom")


def test_composite_merges_news_and_sorts_newest_first():
    older = {"title": "Old", "report_date": "2026-02-01T00:00:00Z"}
    newer = {"title": "New", "report_date": "2026-02-03T00:00:00Z"}
    yf = FakeSource(news=[older])
    db = FakeSource(news=[newer])
    composite = CompositeSource(yf, db)
    result = composite.news("TSLA")
    assert [r["title"] for r in result] == ["New", "Old"]


def test_composite_dedupes_headlines():
    a = {"title": "Same Story", "report_date": "2026-02-01T00:00:00Z", "publisher": "a"}
    b = {"title": "same story", "report_date": "2026-02-02T00:00:00Z", "publisher": "b"}
    composite = CompositeSource(FakeSource(news=[a]), FakeSource(news=[b]))
    result = composite.news("TSLA")
    assert len(result) == 1
    assert result[0]["publisher"] == "a"


def test_composite_respects_limit():
    items = [{"title": f"t{i}", "report_date": f"2026-02-{i+1:02d}T00:00:00Z"} for i in range(5)]
    composite = CompositeSource(FakeSource(news=items))
    assert len(composite.news("TSLA", limit=2)) == 2


def test_composite_calendar_merges_by_date():
    a = {"report_date": "2026-04-23", "source": "yfinance"}
    b = {"report_date": "2026-04-23", "source": "defeatbeta"}
    c = {"report_date": "2026-07-30", "source": "defeatbeta"}
    composite = CompositeSource(FakeSource(earnings_calendar=[a]), FakeSource(earnings_calendar=[b, c]))
    result = composite.earnings_calendar("TSLA")
    assert [r["report_date"] for r in result] == ["2026-04-23", "2026-07-30"]
    assert result[0]["source"] == "yfinance"


def test_composite_first_source_with_data_wins():
    yf = FakeSource(price=[{"close": 250.0}])
    db = FakeSource(price=[{"close": 999.0}], filings=[{"form": "10-K"}])
    composite = CompositeSource(yf, db)
    assert composite.price("TSLA")[0]["close"] == 250.0
    assert composite.filings("TSLA")[0]["form"] == "10-K"


def test_composite_profile_prefers_first_nonempty():
    composite = CompositeSource(FakeSource(profile={}), FakeSource(profile={"longName": "Tesla"}))
    assert composite.profile("TSLA")["longName"] == "Tesla"


def test_composite_collects_errors_without_raising():
    composite = CompositeSource(BrokenSource(), FakeSource(news=[{"title": "ok", "report_date": "2026-02-01"}]))
    result = composite.news("TSLA")
    assert [r["title"] for r in result] == ["ok"]
    assert "BrokenSource: boom" in composite.errors
    assert "boom" in composite.last_error


def test_composite_available_is_any_source():
    assert CompositeSource(BrokenSource(), FakeSource()).available is True
    assert CompositeSource(BrokenSource()).available is False


def test_composite_requires_at_least_one_source():
    with pytest.raises(ValueError):
        CompositeSource()


def test_build_default_source_wraps_both_adapters():
    composite = build_default_source()
    assert isinstance(composite, CompositeSource)
    assert len(composite.sources) == 2
    assert any(isinstance(s, YFinanceSource) for s in composite.sources)


def _install_fake_yfinance():
    module = types.ModuleType("yfinance")

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

    fake_ticker = FakeTicker("TSLA")
    fake_ticker.news = [
        {
            "id": "n1",
            "content": {
                "title": "Tesla deliveries beat",
                "summary": "Deliveries topped estimates",
                "pubDate": "2026-02-03T14:30:00Z",
                "provider": {"displayName": "Reuters"},
                "clickThroughUrl": {"url": "https://example.com/a"},
                "finance": {"stockTickers": [{"symbol": "TSLA"}, {"symbol": "RIVN"}, {"symbol": None}]},
            },
        },
        {
            "id": "n2",
            "content": {"title": "", "pubDate": "2026-02-03T14:00:00Z"},
        },
        {
            "title": "Legacy headline",
            "publisher": "Bloomberg",
            "providerPublishTime": 1770000000,
            "link": "https://example.com/b",
            "summary": "legacy shape",
        },
    ]
    fake_ticker.info = {"longName": "Tesla, Inc.", "sector": "Consumer Cyclical", "marketCap": 7e11}
    fake_ticker.calendar = {"Earnings Date": [types.SimpleNamespace(isoformat=lambda: "2026-04-23T00:00:00")]}

    module.Ticker = lambda symbol: fake_ticker
    sys.modules["yfinance"] = module
    return fake_ticker


def test_yfinance_news_new_shape():
    _install_fake_yfinance()
    records = YFinanceSource().news("TSLA")
    assert len(records) == 2
    first = records[0]
    assert first["title"] == "Tesla deliveries beat"
    assert first["publisher"] == "Reuters"
    assert first["report_date"] == "2026-02-03T14:30:00Z"
    assert first["link"] == "https://example.com/a"
    assert first["summary"] == "Deliveries topped estimates"
    assert first["tickers"] == ["TSLA", "RIVN"]


def test_yfinance_news_legacy_shape():
    _install_fake_yfinance()
    records = YFinanceSource().news("TSLA")
    legacy = records[1]
    assert legacy["title"] == "Legacy headline"
    assert legacy["publisher"] == "Bloomberg"
    assert legacy["tickers"] == []
    assert "T" in legacy["report_date"]


def test_yfinance_profile_and_calendar():
    _install_fake_yfinance()
    source = YFinanceSource()
    assert source.profile("TSLA")["longName"] == "Tesla, Inc."
    assert source.earnings_calendar("TSLA")[0]["report_date"] == "2026-04-23"


def test_yfinance_empty_methods():
    _install_fake_yfinance()
    source = YFinanceSource()
    assert source.filings("TSLA") == []
    assert source.transcripts_catalog("TSLA") == []
    assert source.transcript("TSLA", 2026, 1) == []
    assert source.quarterly_income_statement("TSLA") == []
