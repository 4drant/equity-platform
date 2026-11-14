# equity-platform

Autonomous equity research loop platform: per-ticker research agents, catalyst tracking, a
cross-ticker relationship graph, and citation-verified written research.

Data comes from a composite of two open sources, merged behind one interface
(`equity_platform/data/factory.py`):

- **[yfinance](https://github.com/ranaroussi/yfinance)** — fresh news (minutes old), live prices,
  upcoming earnings dates, company profile. Best for anything that must be current.
- **[defeatbeta-api](https://github.com/defeat-beta/defeatbeta-api)** — an open-source Yahoo Finance
  alternative on Hugging Face (no API key, no rate limits): SEC filings, earnings call transcripts,
  quarterly financial statements, historical prices and calendars. Best for anything structured
  and historical.

`CompositeSource` merges news from both (deduped by headline, newest first), merges earnings
calendars by date, and takes the first source with data for filings, transcripts, statements,
profile, and prices. Per-source failures are collected in `composite.errors` and never break a run.

## Architecture

```
CompositeSource (YFinance fresh news/prices + DefeatBeta filings/transcripts/statements)
        │
   Ingestor ──► Extractor ──► Store (SQLite: signals, catalysts, theses, reports, edges)
        │             │
     Sentinel     ThesisKeeper ──► conviction + invalidation triggers
        │             │
   Cartographer ──► GraphEngine (propagation, clusters, competitor context)
        │
      Writer ──► Critic (citation gate) ──► Reports (flash notes, digests, briefs)
        │
   Portfolio (triage queue, fan-out alerts, consistency flags, weekly brief)
```

Every published claim must cite a stored signal (`[S:<id>]`); the Critic fails any report whose
citations do not resolve. That is the platform's trust invariant.

## Install

```bash
pip install -e ".[dev]"
```

## Quickstart

```bash
equity add TSLA AAPL NVDA
equity run                      # one research cycle per watchlist ticker
equity queue                    # global triage queue across tickers
equity graph --node TSLA        # relationship edges
equity graph --node TSLA --propagate   # fan-out impact ranking
equity brief                    # cross-portfolio brief with clusters + consistency flags
equity reports TSLA             # generated reports
equity serve                    # FastAPI on 127.0.0.1:8000 (/docs for OpenAPI)
```

API endpoints: `POST /watchlist`, `GET /tickers/{sym}`, `GET /tickers/{sym}/thesis`,
`GET /tickers/{sym}/reports`, `GET /graph`, `GET /graph/propagate`, `GET /queue`,
`POST /reports/generate`, `GET /reports/portfolio`, `GET /health`.

## Configuration (env)

| Variable | Purpose |
|---|---|
| `EQUITY_DB_PATH` | SQLite database path (default `equity.db`) |
| `EQUITY_WATCHLIST` | Comma-separated default tickers |
| `EQUITY_LLM_BASE_URL` / `EQUITY_LLM_API_KEY` / `EQUITY_LLM_MODEL` | Optional LLM (any OpenAI-compatible endpoint). Without it, deterministic heuristics run. |
| `EQUITY_DAILY_TOKEN_BUDGET` | Per-run token budget guard |

See `.env.example`.

## LLM

Agents work with **zero configuration** using rule-based heuristics. Set an OpenAI-compatible
endpoint to upgrade classification/extraction/writing to LLM calls; every agent falls back to
heuristics on any LLM failure.

## Tests

```bash
pytest -q
```

## Scheduling (production)

Run `equity run` on a cron/every-N-minutes loop; `equity brief` weekly; catalyst proximity
alerts fire inside each cycle at T-14/T-7/T-1/T-0. For durable workflows, wrap `Portfolio.run`
in Temporal or Celery — the loop is idempotent (signals dedupe by content hash).

## Disclaimer

AI-generated research output. Not investment advice.
