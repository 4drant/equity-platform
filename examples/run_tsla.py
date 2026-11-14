"""One full research cycle for TSLA using DefeatBeta data.

Usage:
    python examples/run_tsla.py
"""
from equity_platform.config import settings
from equity_platform.data.defeatbeta import DefeatBetaSource
from equity_platform.llm.client import llm_from_env
from equity_platform.portfolio import Portfolio
from equity_platform.store.sqlite import Store


def main() -> None:
    store = Store(settings.db_path)
    source = DefeatBetaSource()
    print(f"defeatbeta available: {source.available}")
    portfolio = Portfolio(store, llm_from_env(settings), source)
    portfolio.add("TSLA")
    results = portfolio.run(["TSLA"])
    print(results)
    brief = portfolio.weekly_brief()
    print(brief.body_md)


if __name__ == "__main__":
    main()
