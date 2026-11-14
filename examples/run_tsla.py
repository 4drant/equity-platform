"""One full research cycle for TSLA using the composite data layer.

Usage:
    python examples/run_tsla.py
"""
from equity_platform.config import settings
from equity_platform.data.factory import build_default_source
from equity_platform.llm.client import llm_from_env
from equity_platform.portfolio import Portfolio
from equity_platform.store.sqlite import Store


def main() -> None:
    store = Store(settings.db_path)
    source = build_default_source()
    print(f"composite available: {source.available} (sources: {[type(s).__name__ for s in source.sources]})")
    portfolio = Portfolio(store, llm_from_env(settings), source)
    portfolio.add("TSLA")
    results = portfolio.run(["TSLA"])
    print(results)
    brief = portfolio.weekly_brief()
    print(brief.body_md)


if __name__ == "__main__":
    main()
