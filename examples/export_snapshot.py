"""Export an interactive static snapshot of the dashboard (graph data baked in).

Produces dist/index.html — deployable to GitHub Pages or any static host.

Usage:
    python examples/export_snapshot.py [db_path] [out_path]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from equity_platform.llm.client import llm_from_env
from equity_platform.portfolio import Portfolio
from equity_platform.store.sqlite import Store
from equity_platform.ui import DASHBOARD_HTML

INIT_MARKER = "(async function init() {"
INIT_END = "})();"
SCRIPT_MARKER = "<script>\nconst EDGE_COLORS"

STATIC_INIT = """(async function init() {
  resize(); legend(); loop();
  const health = DATA.health;
  const el = document.getElementById("health");
  el.textContent = "data " + (health.data_source ? "ok" : "down") + " \\u00b7 llm " + (health.llm ? "ok" : "heuristic") +
    " \\u00b7 " + (health.tickers || []).length + " tickers \\u00b7 snapshot";
  el.classList.add("ok");
  document.getElementById("watchlist").textContent = (health.tickers || []).join(", ") || "\\u2014";
  buildGraph(DATA.edges, health.tickers);
  renderQueue(DATA.queue);
})();"""


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "equity.db"
    out_path = Path(sys.argv[2] if len(sys.argv) > 2 else "dist/index.html")

    store = Store(db_path)
    llm = llm_from_env()
    portfolio = Portfolio(store, llm)
    data = {
        "health": {
            "data_source": True,
            "llm": llm.available,
            "tickers": [e.identity.symbol for e in store.entities()],
        },
        "edges": [
            {"source": e.source, "target": e.target, "type": e.type.value, "strength": e.strength}
            for e in store.edges()
        ],
        "queue": portfolio.triage_queue(20),
    }

    head, rest = DASHBOARD_HTML.split(INIT_MARKER)
    tail_index = rest.index(INIT_END) + len(INIT_END)
    html = head + STATIC_INIT + rest[tail_index:]
    payload = "<script>const DATA = " + json.dumps(data) + ";</script>\n"
    html = html.replace(SCRIPT_MARKER, payload + SCRIPT_MARKER)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    print(f"wrote {out_path} ({len(html)} bytes, {len(data['edges'])} edges, {len(data['queue'])} queue items)")


if __name__ == "__main__":
    main()
