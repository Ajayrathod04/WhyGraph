"""Pure-Python fallbacks for the graph algorithms.

The product asks FalkorDB first (Cypher variable-length paths, algo.pageRank, shortestPath).
If the installed FalkorDB version rejects one of those calls, the same answer is computed here from
edges that were READ FROM the graph, and the receipt says "python-fallback" so nothing is hidden.
The data itself always comes from FalkorDB: this module cannot work without it.
"""
from collections import deque


def adjacency(edges):
    """edges: [(a, b)] meaning a DEPENDS_ON b. Returns (depends_on, dependents) maps."""
    out, inc = {}, {}
    for a, b in edges:
        out.setdefault(a, []).append(b)
        inc.setdefault(b, []).append(a)
    return out, inc


def blast_radius(edges, root, max_hops=4):
    """Systems that (transitively) depend on `root`, with their minimum hop distance."""
    _, dependents = adjacency(edges)
    seen = {root: 0}
    queue = deque([root])
    while queue:
        node = queue.popleft()
        if seen[node] >= max_hops:
            continue
        for nxt in dependents.get(node, []):
            if nxt not in seen:
                seen[nxt] = seen[node] + 1
                queue.append(nxt)
    seen.pop(root)
    return seen


def pagerank(edges, damping=0.85, iterations=40):
    """PageRank over the DEPENDS_ON graph (a -> b means a depends on b, so b collects rank)."""
    nodes = sorted({n for e in edges for n in e})
    if not nodes:
        return {}
    out, _ = adjacency(edges)
    rank = {n: 1.0 / len(nodes) for n in nodes}
    for _ in range(iterations):
        nxt = {n: (1.0 - damping) / len(nodes) for n in nodes}
        for n in nodes:
            targets = out.get(n, [])
            if targets:
                share = damping * rank[n] / len(targets)
                for t in targets:
                    nxt[t] += share
            else:
                for m in nodes:
                    nxt[m] += damping * rank[n] / len(nodes)
        rank = nxt
    return rank


def shortest_path(edges, src, dst):
    """Shortest chain src -> ... -> dst following DEPENDS_ON. Returns a list of ids or None."""
    out, _ = adjacency(edges)
    prev = {src: None}
    queue = deque([src])
    while queue:
        node = queue.popleft()
        if node == dst:
            path = []
            while node is not None:
                path.append(node)
                node = prev[node]
            return list(reversed(path))
        for nxt in out.get(node, []):
            if nxt not in prev:
                prev[nxt] = node
                queue.append(nxt)
    return None
