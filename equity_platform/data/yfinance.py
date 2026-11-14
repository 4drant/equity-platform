from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _epoch_to_iso(value: Any) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    return str(value or "")


class YFinanceSource:
    """Adapter over yfinance: fresh news, live prices, upcoming earnings, profile.

    Degrades gracefully: if the package is missing or a call fails, methods return
    empty results and set ``last_error``.
    """

    def __init__(self) -> None:
        self.last_error: str = ""
        self._yf = None
        try:
            import yfinance as yf

            self._yf = yf
        except ImportError as exc:
            self.last_error = f"yfinance not installed: {exc}"

    @property
    def available(self) -> bool:
        return self._yf is not None

    def _ticker(self, symbol: str) -> Any:
        if not self._yf:
            raise RuntimeError(self.last_error)
        return self._yf.Ticker(symbol.upper())

    def _safe(self, fn, default: Any) -> Any:
        try:
            return fn()
        except Exception as exc:
            self.last_error = f"yfinance call failed: {exc}"
            return default

    def _news_records(self, symbol: str) -> list[dict[str, Any]]:
        news = self._safe(lambda: self._ticker(symbol).news, [])
        records = []
        for item in news or []:
            content = item.get("content") if isinstance(item, dict) else None
            if isinstance(content, dict):
                provider = content.get("provider") or {}
                url_obj = content.get("clickThroughUrl") or content.get("canonicalUrl") or {}
                tickers = [
                    t.get("symbol", "").upper()
                    for t in (content.get("finance") or {}).get("stockTickers", [])
                    if t.get("symbol")
                ]
                records.append(
                    {
                        "title": str(content.get("title") or ""),
                        "publisher": str(provider.get("displayName") or "yahoo"),
                        "report_date": str(content.get("pubDate") or content.get("displayTime") or ""),
                        "link": str(url_obj.get("url") or ""),
                        "summary": str(content.get("summary") or ""),
                        "tickers": tickers,
                    }
                )
            elif isinstance(item, dict):
                records.append(
                    {
                        "title": str(item.get("title") or ""),
                        "publisher": str(item.get("publisher") or "yahoo"),
                        "report_date": _epoch_to_iso(item.get("providerPublishTime")),
                        "link": str(item.get("link") or ""),
                        "summary": str(item.get("summary") or ""),
                        "tickers": [],
                    }
                )
        return [r for r in records if r["title"]]

    def news(self, symbol: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._news_records(symbol)[:limit]

    def filings(self, symbol: str, limit: int = 10) -> list[dict[str, Any]]:
        return []

    def profile(self, symbol: str) -> dict[str, Any]:
        info = self._safe(lambda: self._ticker(symbol).info, {}) or {}
        if not info:
            return {}
        return {
            "symbol": symbol.upper(),
            "longName": info.get("longName") or info.get("shortName") or "",
            "sector": info.get("sector") or "",
            "industry": info.get("industry") or "",
            "exchange": info.get("exchange") or "",
            "marketCap": info.get("marketCap"),
        }

    def price(self, symbol: str, limit: int = 30) -> list[dict[str, Any]]:
        frame = self._safe(lambda: self._ticker(symbol).history(period="3mo"), None)
        if frame is None or len(frame) == 0:
            return []
        records = []
        for index, row in frame.iterrows():
            records.append(
                {
                    "symbol": symbol.upper(),
                    "report_date": str(index.date()) if hasattr(index, "date") else str(index),
                    "open": float(row["Open"]),
                    "close": float(row["Close"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "volume": int(row["Volume"]),
                }
            )
        return records[-limit:]

    def earnings_calendar(self, symbol: str) -> list[dict[str, Any]]:
        calendar = self._safe(lambda: self._ticker(symbol).calendar, {}) or {}
        dates = calendar.get("Earnings Date") or []
        if not isinstance(dates, list):
            dates = [dates]
        rows = []
        for value in dates:
            iso = value.isoformat() if hasattr(value, "isoformat") else str(value)
            rows.append(
                {
                    "symbol": symbol.upper(),
                    "report_date": iso[:10],
                    "name": calendar.get("company") or symbol.upper(),
                    "fiscal_quarter_ending": "",
                    "source": "yfinance",
                }
            )
        return rows

    def transcripts_catalog(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def transcript(self, symbol: str, fiscal_year: int, fiscal_quarter: int) -> list[dict[str, Any]]:
        return []

    def quarterly_income_statement(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def quarterly_balance_sheet(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def quarterly_cash_flow(self, symbol: str) -> list[dict[str, Any]]:
        return []
