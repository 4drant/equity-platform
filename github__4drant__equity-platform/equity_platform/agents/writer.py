from __future__ import annotations

import uuid
from datetime import datetime

from equity_platform.agents.base import Agent
from equity_platform.models.catalysts import Catalyst
from equity_platform.models.reports import Report, ReportType
from equity_platform.models.signals import Signal
from equity_platform.models.thesis import Thesis

DISCLAIMER = (
    "\n---\n*AI-generated research. Not investment advice. All claims cite stored signals as [S:<id>].*"
)


class Writer(Agent):
    name = "writer"

    def flash_note(self, ticker: str, signal: Signal, peers: list[str] | None = None) -> Report:
        peers = peers or []
        peer_line = ", ".join(peers) if peers else "none mapped yet"
        body = (
            f"# Flash note: {ticker.upper()} — {signal.headline}\n\n"
            f"**Classification:** {signal.classification.value} (confidence {signal.confidence:.2f})\n"
            f"**Sentiment score:** {signal.sentiment:+.2f}\n"
            f"**Source:** [{signal.source}]({signal.url or 'n/a'})\n\n"
            f"## What happened\n{signal.quote or signal.headline} [S:{signal.id}]\n\n"
            f"## Extracted facts\n"
            + ("\n".join(f"- {f} [S:{signal.id}]" for f in signal.facts) or "- No quantified facts extracted.")
            + f"\n\n## Peer context\nConnected tickers: {peer_line}.\n"
            + DISCLAIMER
        )
        return Report(
            id=f"rep-{uuid.uuid4().hex[:12]}",
            tickers=[ticker.upper()],
            type=ReportType.FLASH_NOTE,
            title=f"{ticker.upper()}: {signal.headline[:90]}",
            body_md=body,
            cited_signal_ids=[signal.id],
        )

    def daily_digest(
        self,
        ticker: str,
        signals: list[Signal],
        catalysts: list[Catalyst],
        thesis: Thesis | None,
        alerts: list[dict] | None = None,
    ) -> Report:
        alerts = alerts or []
        cited = [s.id for s in signals]
        lines = [f"# Daily digest: {ticker.upper()} — {datetime.now().date().isoformat()}\n"]
        if thesis:
            fired = thesis.fired_triggers()
            lines.append(f"**Conviction:** {thesis.conviction}/100")
            if fired:
                lines.append(
                    "**Invalidation triggers fired:** "
                    + ", ".join(t.description for t in fired)
                )
            lines.append("")
        if signals:
            lines.append("## New signals\n")
            for s in signals[:20]:
                lines.append(
                    f"- **[{s.classification.value}]** {s.headline} "
                    f"(sentiment {s.sentiment:+.2f}) [S:{s.id}]"
                )
        else:
            lines.append("## New signals\n\nNo new signals in this cycle.")
        if catalysts:
            lines.append("\n## Catalyst calendar\n")
            for c in catalysts:
                date_str = c.expected_date.isoformat() if c.expected_date else "TBD"
                lines.append(f"- {date_str} **{c.type.value}** {c.title} ({c.status.value})")
        if alerts:
            lines.append("\n## Proximity alerts\n")
            for a in alerts:
                lines.append(f"- **{a['window']}** {a['title']} (expected {a['expected_date']})")
        lines.append(DISCLAIMER)
        return Report(
            id=f"rep-{uuid.uuid4().hex[:12]}",
            tickers=[ticker.upper()],
            type=ReportType.DAILY_DIGEST,
            title=f"{ticker.upper()} daily digest {datetime.now().date().isoformat()}",
            body_md="\n".join(lines),
            cited_signal_ids=cited,
        )

    def portfolio_brief(
        self, entries: list[dict], flags: list[str], clusters: list[set[str]]
    ) -> Report:
        lines = [f"# Portfolio brief — {datetime.now().date().isoformat()}\n"]
        lines.append("| Ticker | Conviction | Material signals | Open catalysts |")
        lines.append("|---|---|---|---|")
        for e in entries:
            lines.append(
                f"| {e['ticker']} | {e['conviction']} | {e['material_signals']} | {e['open_catalysts']} |"
            )
        if clusters:
            lines.append("\n## Detected clusters\n")
            for cluster in clusters:
                lines.append("- " + ", ".join(sorted(cluster)))
        if flags:
            lines.append("\n## Consistency flags\n")
            for flag in flags:
                lines.append(f"- {flag}")
        lines.append(DISCLAIMER)
        return Report(
            id=f"rep-{uuid.uuid4().hex[:12]}",
            tickers=[e["ticker"] for e in entries],
            type=ReportType.PORTFOLIO_BRIEF,
            title=f"Portfolio brief {datetime.now().date().isoformat()}",
            body_md="\n".join(lines),
            cited_signal_ids=[],
        )

    def postmortem(self, ticker: str, catalyst: Catalyst, thesis: Thesis | None, price_move: float | None) -> Report:
        if price_move is None:
            grade = "UNGRADED"
            outcome = "Price data unavailable; grade manually."
        else:
            direction_ok = (catalyst.expected_impact >= 0) == (price_move >= 0)
            grade = "HIT" if direction_ok else "MISS"
            outcome = f"Actual price move over event window: {price_move:+.2%}."
        body = (
            f"# Catalyst post-mortem: {ticker.upper()} — {catalyst.title}\n\n"
            f"**Type:** {catalyst.type.value}\n"
            f"**Expected date:** {catalyst.expected_date}\n"
            f"**Expected impact:** {catalyst.expected_impact:+.2f}\n"
            f"**Grade:** {grade}\n\n{outcome}\n"
            + (f"\n**Conviction at event:** {thesis.conviction}/100\n" if thesis else "")
            + DISCLAIMER
        )
        return Report(
            id=f"rep-{uuid.uuid4().hex[:12]}",
            tickers=[ticker.upper()],
            type=ReportType.CATALYST_POSTMORTEM,
            title=f"{ticker.upper()} post-mortem: {catalyst.title[:80]}",
            body_md=body,
            cited_signal_ids=[catalyst.source_signal_id] if catalyst.source_signal_id else [],
        )
