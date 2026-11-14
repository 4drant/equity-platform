from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Any

from equity_platform.models.catalysts import Catalyst
from equity_platform.models.entity import TickerEntity
from equity_platform.models.graph import Relationship
from equity_platform.models.reports import Report
from equity_platform.models.signals import Signal, utcnow
from equity_platform.models.thesis import Thesis

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    ts TEXT NOT NULL,
    source TEXT NOT NULL,
    url TEXT DEFAULT '',
    headline TEXT DEFAULT '',
    quote TEXT DEFAULT '',
    classification TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    facts TEXT DEFAULT '[]',
    tickers_mentioned TEXT DEFAULT '[]',
    raw_hash TEXT DEFAULT '',
    sentiment REAL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker, ts);
CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_hash ON signals(ticker, raw_hash);

CREATE TABLE IF NOT EXISTS catalysts (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    expected_date TEXT,
    status TEXT NOT NULL,
    expected_impact REAL DEFAULT 0.0,
    resolution TEXT DEFAULT '',
    outcome TEXT DEFAULT '',
    source_signal_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS theses (
    ticker TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    conviction INTEGER DEFAULT 50,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    tickers TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    body_md TEXT NOT NULL,
    cited_signal_ids TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    verdict TEXT DEFAULT 'pending',
    issues TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS edges (
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    type TEXT NOT NULL,
    strength REAL DEFAULT 0.5,
    evidence_signal_ids TEXT DEFAULT '[]',
    PRIMARY KEY (source, target, type)
);

CREATE TABLE IF NOT EXISTS entities (
    symbol TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    agent TEXT NOT NULL,
    ticker TEXT DEFAULT '',
    detail TEXT DEFAULT '',
    tokens_used INTEGER DEFAULT 0
);
"""


def _dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


class Store:
    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    def commit(self) -> None:
        with self.lock:
            self.conn.commit()

    def save_signal(self, signal: Signal) -> bool:
        try:
            self.conn.execute(
                "INSERT INTO signals (id, ticker, ts, source, url, headline, quote, classification,"
                " confidence, facts, tickers_mentioned, raw_hash, sentiment)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    signal.id,
                    signal.ticker.upper(),
                    _dt(signal.ts),
                    signal.source,
                    signal.url,
                    signal.headline,
                    signal.quote,
                    signal.classification.value,
                    signal.confidence,
                    json.dumps(signal.facts),
                    json.dumps([t.upper() for t in signal.tickers_mentioned]),
                    signal.raw_hash,
                    signal.sentiment,
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_signal(self, signal_id: str) -> Signal | None:
        row = self.conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
        return self._row_to_signal(row) if row else None

    @staticmethod
    def _row_to_signal(row: sqlite3.Row) -> Signal:
        return Signal(
            id=row["id"],
            ticker=row["ticker"],
            ts=datetime.fromisoformat(row["ts"]),
            source=row["source"],
            url=row["url"],
            headline=row["headline"],
            quote=row["quote"],
            classification=row["classification"],
            confidence=row["confidence"],
            facts=json.loads(row["facts"]),
            tickers_mentioned=json.loads(row["tickers_mentioned"]),
            raw_hash=row["raw_hash"],
            sentiment=row["sentiment"],
        )

    def signals_for(
        self,
        ticker: str,
        since: datetime | None = None,
        classification: str | None = None,
        limit: int = 500,
    ) -> list[Signal]:
        query = "SELECT * FROM signals WHERE ticker = ?"
        params: list[Any] = [ticker.upper()]
        if since is not None:
            query += " AND ts >= ?"
            params.append(since.isoformat())
        if classification:
            query += " AND classification = ?"
            params.append(classification)
        query += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        return [self._row_to_signal(r) for r in self.conn.execute(query, params)]

    def all_signals(self, limit: int = 2000) -> list[Signal]:
        rows = self.conn.execute("SELECT * FROM signals ORDER BY ts DESC LIMIT ?", (limit,))
        return [self._row_to_signal(r) for r in rows]

    def save_catalyst(self, catalyst: Catalyst) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO catalysts (id, ticker, type, title, expected_date, status,"
            " expected_impact, resolution, outcome, source_signal_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                catalyst.id,
                catalyst.ticker.upper(),
                catalyst.type.value,
                catalyst.title,
                catalyst.expected_date.isoformat() if catalyst.expected_date else None,
                catalyst.status.value,
                catalyst.expected_impact,
                catalyst.resolution,
                catalyst.outcome,
                catalyst.source_signal_id,
            ),
        )
        self.conn.commit()

    def catalysts_for(self, ticker: str, status: str | None = None) -> list[Catalyst]:
        query = "SELECT * FROM catalysts WHERE ticker = ?"
        params: list[Any] = [ticker.upper()]
        if status:
            query += " AND status = ?"
            params.append(status)
        out = []
        for row in self.conn.execute(query, params):
            out.append(
                Catalyst(
                    id=row["id"],
                    ticker=row["ticker"],
                    type=row["type"],
                    title=row["title"],
                    expected_date=row["expected_date"],
                    status=row["status"],
                    expected_impact=row["expected_impact"],
                    resolution=row["resolution"],
                    outcome=row["outcome"],
                    source_signal_id=row["source_signal_id"],
                )
            )
        return out

    def save_thesis(self, thesis: Thesis) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO theses (ticker, data, conviction, updated_at) VALUES (?,?,?,?)",
            (
                thesis.ticker.upper(),
                thesis.model_dump_json(),
                thesis.conviction,
                _dt(thesis.updated_at),
            ),
        )
        self.conn.commit()

    def get_thesis(self, ticker: str) -> Thesis | None:
        row = self.conn.execute(
            "SELECT data FROM theses WHERE ticker = ?", (ticker.upper(),)
        ).fetchone()
        if not row:
            return None
        return Thesis.model_validate_json(row["data"])

    def save_report(self, report: Report) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO reports (id, tickers, type, title, body_md, cited_signal_ids,"
            " created_at, verdict, issues) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                report.id,
                json.dumps([t.upper() for t in report.tickers]),
                report.type.value,
                report.title,
                report.body_md,
                json.dumps(report.cited_signal_ids),
                _dt(report.created_at),
                report.verdict,
                json.dumps(report.issues),
            ),
        )
        self.conn.commit()

    def reports_for(self, ticker: str, limit: int = 50) -> list[Report]:
        rows = self.conn.execute(
            "SELECT * FROM reports ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        out = []
        for row in rows:
            if ticker.upper() in json.loads(row["tickers"]):
                out.append(
                    Report(
                        id=row["id"],
                        tickers=json.loads(row["tickers"]),
                        type=row["type"],
                        title=row["title"],
                        body_md=row["body_md"],
                        cited_signal_ids=json.loads(row["cited_signal_ids"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        verdict=row["verdict"],
                        issues=json.loads(row["issues"]),
                    )
                )
        return out

    def save_edge(self, edge: Relationship) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO edges (source, target, type, strength, evidence_signal_ids)"
            " VALUES (?,?,?,?,?)",
            (
                edge.source.upper(),
                edge.target.upper(),
                edge.type.value,
                edge.strength,
                json.dumps(edge.evidence_signal_ids),
            ),
        )
        self.conn.commit()

    def edges(self) -> list[Relationship]:
        rows = self.conn.execute("SELECT * FROM edges")
        return [
            Relationship(
                source=r["source"],
                target=r["target"],
                type=r["type"],
                strength=r["strength"],
                evidence_signal_ids=json.loads(r["evidence_signal_ids"]),
            )
            for r in rows
        ]

    def save_entity(self, entity: TickerEntity) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO entities (symbol, data, updated_at) VALUES (?,?,?)",
            (entity.identity.symbol.upper(), entity.model_dump_json(), _dt(entity.updated_at)),
        )
        self.conn.commit()

    def entities(self) -> list[TickerEntity]:
        rows = self.conn.execute("SELECT data FROM entities")
        return [TickerEntity.model_validate_json(r["data"]) for r in rows]

    def log_run(self, agent: str, ticker: str = "", detail: str = "", tokens_used: int = 0) -> None:
        self.conn.execute(
            "INSERT INTO run_log (ts, agent, ticker, detail, tokens_used) VALUES (?,?,?,?,?)",
            (_dt(utcnow()), agent, ticker.upper(), detail, tokens_used),
        )
        self.conn.commit()

    def known_tickers(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT ticker FROM signals UNION SELECT symbol FROM entities"
        )
        return sorted({r[0].upper() for r in rows if r[0]})


def _synchronized(method):
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)

    return wrapper


for _name, _fn in list(vars(Store).items()):
    if _name.startswith("__") or isinstance(_fn, (staticmethod, classmethod)):
        continue
    if callable(_fn):
        setattr(Store, _name, _synchronized(_fn))
