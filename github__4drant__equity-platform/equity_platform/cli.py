from __future__ import annotations

import argparse
import json
import sys

from equity_platform.config import settings
from equity_platform.data.defeatbeta import DefeatBetaSource
from equity_platform.llm.client import llm_from_env
from equity_platform.portfolio import Portfolio
from equity_platform.store.sqlite import Store


def _portfolio(db: str | None = None) -> Portfolio:
    store = Store(db or settings.db_path)
    return Portfolio(store, llm_from_env(settings), DefeatBetaSource())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="equity", description="Autonomous equity research loop")
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="add a ticker to the watchlist")
    add_p.add_argument("tickers", nargs="+")

    run_p = sub.add_parser("run", help="run research loop cycles")
    run_p.add_argument("--ticker", action="append", default=[], help="specific tickers; default = watchlist")
    run_p.add_argument("--db", default=None)

    queue_p = sub.add_parser("queue", help="show global triage queue")
    queue_p.add_argument("--limit", type=int, default=20)
    queue_p.add_argument("--db", default=None)

    graph_p = sub.add_parser("graph", help="show relationship graph")
    graph_p.add_argument("--node", default="")
    graph_p.add_argument("--propagate", action="store_true", help="fan-out impact from --node")
    graph_p.add_argument("--db", default=None)

    brief_p = sub.add_parser("brief", help="generate portfolio brief")
    brief_p.add_argument("--db", default=None)

    reports_p = sub.add_parser("reports", help="list reports for a ticker")
    reports_p.add_argument("ticker")
    reports_p.add_argument("--db", default=None)

    serve_p = sub.add_parser("serve", help="start the API server")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)

    if args.command == "add":
        pf = _portfolio(args.db)
        for t in args.tickers:
            pf.add(t)
            print(f"added {t.upper()}")
        return 0

    if args.command == "run":
        pf = _portfolio(args.db)
        for ticker in args.ticker:
            pf.add(ticker)
        results = pf.run(args.ticker or None)
        print(json.dumps(results, indent=2, default=str))
        return 0

    if args.command == "queue":
        pf = _portfolio(args.db)
        print(json.dumps(pf.triage_queue(args.limit), indent=2, default=str))
        return 0

    if args.command == "graph":
        pf = _portfolio(args.db)
        if args.propagate and args.node:
            print(json.dumps(pf.graph.propagate(args.node, -0.5), indent=2, default=str))
        else:
            for edge in pf.graph.edges_for_all():
                if not args.node or args.node.upper() in (edge.source, edge.target):
                    print(f"{edge.source} --[{edge.type.value} {edge.strength:.2f}]--> {edge.target}")
        return 0

    if args.command == "brief":
        pf = _portfolio(args.db)
        report = pf.weekly_brief()
        print(f"{report.title} (verdict: {report.verdict})\n")
        print(report.body_md)
        return 0

    if args.command == "reports":
        pf = _portfolio(args.db)
        for report in pf.store.reports_for(args.ticker):
            print(f"[{report.verdict:>8}] {report.created_at} {report.type.value}: {report.title}")
        return 0

    if args.command == "serve":
        import uvicorn

        uvicorn.run("equity_platform.api:app", host=args.host, port=args.port)
        return 0

    parser.print_help(sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
