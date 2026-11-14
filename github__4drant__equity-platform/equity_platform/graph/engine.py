from __future__ import annotations

from collections import defaultdict, deque

from equity_platform.models.graph import EdgeType, Relationship


class GraphEngine:
    """In-memory relationship graph rebuilt from the Store."""

    def __init__(self, edges: list[Relationship] | None = None) -> None:
        self._adj: dict[str, list[Relationship]] = defaultdict(list)
        self._edge_keys: dict[tuple, Relationship] = {}
        for edge in edges or []:
            self.add_edge(edge)

    def add_edge(self, edge: Relationship) -> None:
        key = edge.key()
        existing = self._edge_keys.get(key)
        if existing and existing.strength >= edge.strength:
            return
        self._edge_keys[key] = edge
        a, b, _ = key
        self._adj[a].append(edge)
        self._adj[b].append(edge)

    def neighbors(self, node: str) -> list[Relationship]:
        return list(self._adj.get(node.upper(), []))

    def propagate(
        self,
        origin: str,
        impact: float,
        max_depth: int = 2,
        decay: float = 0.5,
        min_score: float = 0.05,
    ) -> list[dict]:
        """BFS fan-out: impacted tickers ranked by decayed signed impact."""
        origin = origin.upper()
        best: dict[str, float] = {}
        queue: deque[tuple[str, float, int, list[str]]] = deque([(origin, impact, 0, [origin])])
        results = []
        while queue:
            node, score, depth, path = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in self._adj.get(node, []):
                other = edge.target.upper() if edge.source.upper() == node else edge.source.upper()
                if other == origin:
                    continue
                propagated = score * decay * edge.strength
                if abs(propagated) < min_score:
                    continue
                if other in best and abs(best[other]) >= abs(propagated):
                    continue
                best[other] = propagated
                results.append(
                    {
                        "ticker": other,
                        "score": round(propagated, 4),
                        "depth": depth + 1,
                        "path": path + [other],
                        "via": edge.type.value,
                    }
                )
                queue.append((other, propagated, depth + 1, path + [other]))
        return sorted(results, key=lambda r: abs(r["score"]), reverse=True)

    def communities(self, min_strength: float = 0.3) -> list[set[str]]:
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for edge in self._edge_keys.values():
            if edge.strength >= min_strength:
                union(edge.source.upper(), edge.target.upper())
        clusters: dict[str, set[str]] = defaultdict(set)
        for node in list(parent):
            clusters[find(node)].add(node)
        return [c for c in clusters.values() if len(c) > 1]

    def competitor_context(self, ticker: str) -> list[str]:
        return [
            edge.target.upper() if edge.source.upper() == ticker.upper() else edge.source.upper()
            for edge in self.neighbors(ticker)
            if edge.type in (EdgeType.COMPETITOR, EdgeType.PEER_GROUP)
        ]

    def edges_for(self, ticker: str) -> list[Relationship]:
        return self.neighbors(ticker)

    def edges_for_all(self) -> list[Relationship]:
        return list(self._edge_keys.values())
