from __future__ import annotations

from typing import Any


class DefeatBetaSource:
    """Adapter over the defeatbeta-api package (https://github.com/defeat-beta/defeatbeta-api).

    Data is served from the defeatbeta/yahoo-finance-data Hugging Face dataset via
    DuckDB with local parquet caching: no API key, no rate limits.

    All methods degrade gracefully: failures return empty results and set ``last_error``.
    """

    def __init__(self) -> None:
        self.last_error: str = ""
        self._ticker_cls = None
        try:
            from defeatbeta_api.data.ticker import Ticker

            self._ticker_cls = Ticker
        except ImportError as exc:
            self.last_error = f"defeatbeta-api not installed: {exc}"

    @property
    def available(self) -> bool:
        return self._ticker_cls is not None

    def _ticker(self, symbol: str) -> Any:
        if not self._ticker_cls:
            raise RuntimeError(self.last_error)
        return self._ticker_cls(symbol.upper())

    def _call_first(self, obj: Any, method_names: list[str], *args: Any) -> Any:
        for name in method_names:
            fn = getattr(obj, name, None)
            if callable(fn):
                try:
                    return fn(*args)
                except Exception as exc:
                    self.last_error = f"{name}: {exc}"
        return None

    @staticmethod
    def _to_records(frame: Any) -> list[dict[str, Any]]:
        if frame is None:
            return []
        if isinstance(frame, list):
            return frame
        try:
            import pandas as pd

            if isinstance(frame, pd.DataFrame):
                return frame.to_dict(orient="records")
        except ImportError:
            pass
        to_dict = getattr(frame, "to_dict", None)
        if callable(to_dict):
            try:
                return to_dict(orient="records")
            except TypeError:
                try:
                    return to_dict()
                except Exception:
                    return []
        return []

    def profile(self, symbol: str) -> dict[str, Any]:
        records = self._to_records(self._call_first(self._ticker(symbol), ["info"]))
        return records[0] if records else {}

    def price(self, symbol: str, limit: int = 30) -> list[dict[str, Any]]:
        frame = self._call_first(self._ticker(symbol), ["price"])
        return self._to_records(frame)[-limit:]

    def news(self, symbol: str, limit: int = 20) -> list[dict[str, Any]]:
        news_obj = self._call_first(self._ticker(symbol), ["news"])
        if news_obj is None:
            return []
        records = self._to_records(self._call_first(news_obj, ["get_news_list"]))
        records = sorted(records, key=lambda r: str(r.get("report_date", "")), reverse=True)
        return records[:limit]

    def filings(self, symbol: str, limit: int = 10) -> list[dict[str, Any]]:
        records = self._to_records(self._call_first(self._ticker(symbol), ["sec_filing"]))
        records = sorted(records, key=lambda r: str(r.get("filing_date", "")), reverse=True)
        return records[:limit]

    def earnings_calendar(self, symbol: str) -> list[dict[str, Any]]:
        return self._to_records(self._call_first(self._ticker(symbol), ["calendar"]))

    def transcripts_catalog(self, symbol: str) -> list[dict[str, Any]]:
        transcripts = self._call_first(self._ticker(symbol), ["earning_call_transcripts"])
        if transcripts is None:
            return []
        return self._to_records(self._call_first(transcripts, ["get_transcripts_list"]))

    def transcript(self, symbol: str, fiscal_year: int, fiscal_quarter: int) -> list[dict[str, Any]]:
        transcripts = self._call_first(self._ticker(symbol), ["earning_call_transcripts"])
        if transcripts is None:
            return []
        frame = self._call_first(transcripts, ["get_transcript"], fiscal_year, fiscal_quarter)
        return self._to_records(frame)

    def quarterly_income_statement(self, symbol: str) -> list[dict[str, Any]]:
        return self._to_records(self._call_first(self._ticker(symbol), ["quarterly_income_statement"]))

    def quarterly_balance_sheet(self, symbol: str) -> list[dict[str, Any]]:
        return self._to_records(self._call_first(self._ticker(symbol), ["quarterly_balance_sheet"]))

    def quarterly_cash_flow(self, symbol: str) -> list[dict[str, Any]]:
        return self._to_records(self._call_first(self._ticker(symbol), ["quarterly_cash_flow"]))
