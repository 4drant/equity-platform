from __future__ import annotations

import re

from equity_platform.agents.base import Agent
from equity_platform.models.reports import Report
from equity_platform.store.sqlite import Store

CITATION_RE = re.compile(r"\[S:([A-Za-z0-9\-]+)\]")


class Critic(Agent):
    name = "critic"

    def verify(self, report: Report, store: Store) -> Report:
        issues: list[str] = []
        for signal_id in report.cited_signal_ids:
            if store.get_signal(signal_id) is None:
                issues.append(f"Unresolved citation [S:{signal_id}]")
        body_citations = set(CITATION_RE.findall(report.body_md))
        for signal_id in body_citations:
            if signal_id not in report.cited_signal_ids:
                issues.append(f"Inline citation [S:{signal_id}] missing from cited_signal_ids")
            elif store.get_signal(signal_id) is None:
                issues.append(f"Inline citation [S:{signal_id}] does not resolve to a stored signal")
        report.issues = issues
        report.verdict = "fail" if issues else "pass"
        store.save_report(report)
        store.log_run(self.name, "", f"{report.id}: {report.verdict} ({len(issues)} issues)")
        return report
