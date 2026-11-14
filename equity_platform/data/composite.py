from __future__ import annotations

from typing import Any


class CompositeSource:
    """Merges multiple data sources behind one interface.

    - news: merged from all sources, deduped by headline, newest first
    - earnings_calendar: merged and deduped by date
    - profile / price / filings / transcripts / statements: first source with data wins
    - per-source failures are collected in ``errors``, never raised
    """

    def __init__(self, *sources: Any) -> None:
        if not sources:
            raise ValueError("CompositeSource needs at least one source")
        self.sources = list(sources)
        self.errors: list[str] = []

    @property
    def available(self) -> bool:
        return any(s.available for s in self.sources)

    @property
    def last_error(self) -> str:
        return "; ".join(self.errors[-5:]) if self.errors else ""

    def _record_error(self, source: Any, exc: Exception) -> None:
        self.errors.append(f"{type(source).__name__}: {exc}")

    def _merge(self, method: str, symbol: str, limit: int | None = None) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for source in self.sources:
            try:
                if limit is None:
                    merged.extend(getattr(source, method)(symbol))
                else:
                    merged.extend(getattr(source, method)(symbol, limit=limit))
            except Exception as exc:
                self._record_error(source, exc)
        return merged

    def _first(self, method: str, symbol: str, limit: int | None = None) -> list[dict[str, Any]]:
        for source in self.sources:
            try:
                if limit is None:
                    records = getattr(source, method)(symbol)
                else:
                    records = getattr(source, method)(symbol, limit=limit)
            except Exception as exc:
                self._record_error(source, exc)
                records = []
            if records:
                return records
        return []

    @staticmethod
    def _dedupe_headline(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out = []
        for record in records:
            key = str(record.get("title", "")).strip().lower()
            if key and key in seen:
                continue
            seen.add(key)
            out.append(record)
        return out

    def news(self, symbol: str, limit: int = 20) -> list[dict[str, Any]]:
        merged = self._dedupe_headline(self._merge("news", symbol, limit=limit))
        return sorted(merged, key=lambda r: str(r.get("report_date", "")), reverse=True)[:limit]

    def filings(self, symbol: str, limit: int = 10) -> list[dict[str, Any]]:
        return self._first("filings", symbol, limit=limit)

    def profile(self, symbol: str) -> dict[str, Any]:
        for source in self.sources:
            try:
                profile = source.profile(symbol)
            except Exception as exc:
                self._record_error(source, exc)
                profile = {}
            if profile:
                return profile
        return {}

    def price(self, symbol: str, limit: int = 30) -> list[dict[str, Any]]:
        return self._first("price", symbol, limit=limit)

    def earnings_calendar(self, symbol: str) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for row in self._merge("earnings_calendar", symbol):
            date = str(row.get("report_date") or "")[:10]
            if date and date not in merged:
                merged[date] = row
        return sorted(merged.values(), key=lambda r: str(r.get("report_date", "")))

    def transcripts_catalog(self, symbol: str) -> list[dict[str, Any]]:
        return self._first("transcripts_catalog", symbol)

    def transcript(self, symbol: str, fiscal_year: int, fiscal_quarter: int) -> list[dict[str, Any]]:
        for source in self.sources:
            try:
                records = source.transcript(symbol, fiscal_year, fiscal_quarter)
            except Exception as exc:
                self._record_error(source, exc)
                records = []
            if records:
                return records
        return []

    def quarterly_income_statement(self, symbol: str) -> list[dict[str, Any]]:
        return self._first("quarterly_income_statement", symbol)

    def quarterly_balance_sheet(self, symbol: str) -> list[dict[str, Any]]:
        return self._first("quarterly_balance_sheet", symbol)

    def quarterly_cash_flow(self, symbol: str) -> list[dict[str, Any]]:
        return self._first("quarterly_cash_flow", symbol)
