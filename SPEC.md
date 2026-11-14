# Equity Platform — Spec

Version 0.1 · Status: Phase 1–4 implemented (single loop, thesis engine, multi-ticker, graph)

## 1. Purpose

Continuous, agentic research loop over equities: each stock is researched autonomously, news and
catalysts are tracked, competitors and relationships are mapped, and citation-verified research is
written — per stock, then generalized across a portfolio with a relationship graph.

## 2. Core concepts

- **Signal** — atomic observed fact from a source, with provenance, classification (material/relevant/noise), sentiment.
- **Catalyst** — dated event expected to move price/thesis (earnings, guidance, regulatory, legal, M&A, product).
- **Thesis** — living document: bull/bear/base legs, assumptions, invalidation triggers, conviction 0–100.
- **Relationship edge** — typed ticker connection: competitor, supplier, customer, peer_group, shared_catalyst, correlation.
- **Report** — flash note, daily digest, weekly update, deep dive, post-mortem, portfolio brief.

## 3. Single-stock loop (atomic unit)

```
INGEST → EXTRACT → UPDATE STATE → DETECT → PRIORITIZE → SYNTHESIZE → WRITE → DELIVER
```

| Stage | Implementation |
|---|---|
| Ingest | `agents/ingest.py` — DefeatBeta news + SEC filings, dedupe by content hash |
| Extract | `agents/extract.py` — LLM or heuristic classification, sentiment, fact extraction, co-mention tickers |
| Detect | `agents/sentinel.py` — catalyst discovery + proximity alerts T-14/7/1/0 |
| Synthesize | `agents/thesis.py` — conviction updates, trigger firing |
| Map | `agents/cartographer.py` — co-mention edges (peer/competitor) persisted to graph |
| Write | `agents/writer.py` — flash notes on material signals, daily digests |
| Gate | `agents/critic.py` — every `[S:<id>]` citation must resolve to a stored signal, else verdict=fail |

## 4. Multi-stock layer

- **Portfolio** (`portfolio.py`): shared loop workers, global triage queue (impact × recency × catalyst boost × sentiment), fan-out alerts via graph propagation, consistency flags (high conviction on both sides of a competitor edge), weekly portfolio brief with clusters.
- **GraphEngine** (`graph/engine.py`): BFS propagation with sign-preserving decay, union-find communities, competitor context for reports.

## 5. Data model

SQLite tables: `signals` (unique per ticker+hash), `catalysts`, `theses` (JSON), `reports`, `edges`, `entities`, `run_log` (append-only audit).

## 6. Non-functional invariants

- Provenance: 100% of published claims cite stored signals; Critic gate blocks failures.
- Idempotency: signal dedupe by content hash; loops safe to re-run.
- Graceful degradation: missing DefeatBeta package or LLM → heuristic mode, never silent gaps.
- Audit: every agent action logged to `run_log` with token usage.

## 7. Roadmap

- P5: sector/pairs agents, cluster-level theses (communities already detected).
- P6: post-mortem calibration loop (post-mortem reports implemented; scorecard pending).
- Dashboard UI over the FastAPI surface; WebSocket stream; Temporal/Celery scheduler.
