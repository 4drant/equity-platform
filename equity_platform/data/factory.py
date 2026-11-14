from __future__ import annotations

from equity_platform.data.composite import CompositeSource
from equity_platform.data.defeatbeta import DefeatBetaSource
from equity_platform.data.yfinance import YFinanceSource


def build_default_source() -> CompositeSource:
    """yfinance first (fresh news, live prices), DefeatBeta second (filings,
    transcripts, statements, historical calendar)."""
    return CompositeSource(YFinanceSource(), DefeatBetaSource())
