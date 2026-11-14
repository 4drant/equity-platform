from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from equity_platform.config import settings
from equity_platform.data.factory import build_default_source
from equity_platform.graph.engine import GraphEngine
from equity_platform.llm.client import llm_from_env
from equity_platform.portfolio import Portfolio
from equity_platform.store.sqlite import Store
from equity_platform.ui import DASHBOARD_HTML

app = FastAPI(title="Equity Platform", version="0.1.0")
store = Store(settings.db_path)
source = build_default_source()
llm = llm_from_env(settings)
portfolio = Portfolio(store, llm, source)


class AddTickerRequest(BaseModel):
    ticker: str


class RunRequest(BaseModel):
    tickers: list[str] = []


@app.get("/ui", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML


@app.post("/watchlist")
def add_ticker(req: AddTickerRequest) -> dict:
    entity = portfolio.add(req.ticker)
    return {"added": entity.identity.symbol}


@app.get("/tickers/{symbol}")
def get_ticker(symbol: str) -> dict:
    signals = store.signals_for(symbol, limit=50)
    return {
        "ticker": symbol.upper(),
        "signals": [s.model_dump(mode="json") for s in signals],
        "catalysts": [c.model_dump(mode="json") for c in store.catalysts_for(symbol)],
    }


@app.get("/tickers/{symbol}/thesis")
def get_thesis(symbol: str) -> dict:
    thesis = store.get_thesis(symbol)
    return {"ticker": symbol.upper(), "thesis": thesis.model_dump(mode="json") if thesis else None}


@app.get("/tickers/{symbol}/reports")
def get_reports(symbol: str) -> dict:
    reports = store.reports_for(symbol)
    return {"ticker": symbol.upper(), "reports": [r.model_dump(mode="json") for r in reports]}


@app.get("/graph")
def get_graph(node: str = "", depth: int = 1) -> dict:
    edges = store.edges()
    if node:
        neighbors = GraphEngine(edges).edges_for(node)
        edges = neighbors
    return {
        "edges": [
            {
                "source": e.source,
                "target": e.target,
                "type": e.type.value,
                "strength": e.strength,
            }
            for e in edges
        ]
    }


@app.get("/graph/propagate")
def propagate(node: str, impact: float = -0.5) -> dict:
    engine = GraphEngine(store.edges())
    return {"origin": node.upper(), "impacts": engine.propagate(node, impact)}


@app.get("/queue")
def queue(limit: int = 20) -> dict:
    return {"queue": portfolio.triage_queue(limit)}


@app.post("/reports/generate")
def generate_reports(req: RunRequest) -> dict:
    return {"runs": portfolio.run(req.tickers or None)}


@app.get("/reports/portfolio")
def portfolio_report() -> dict:
    report = portfolio.weekly_brief()
    return report.model_dump(mode="json")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "data_source": source.available,
        "llm": llm.available,
        "tickers": portfolio.tickers(),
    }
