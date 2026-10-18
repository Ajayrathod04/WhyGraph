"""Verifies every Cypher query and graph algorithm against YOUR live FalkorDB, then runs the full demo flow.

    python scripts/selfcheck.py

It uses throw-away graphs (prefix 'selfcheck_'), so your demo graphs are untouched.
Exit code 0 = everything works. Lines marked WARN mean a graph algorithm is not supported by your FalkorDB
version: the app then uses its documented Python fallback (still reading all data from FalkorDB).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from whygraph import agents, loader  # noqa: E402
from whygraph import queries as Q  # noqa: E402
from whygraph.config import cfg  # noqa: E402
from whygraph.db import Ctx, Store  # noqa: E402

cfg.graph_prefix = "selfcheck_"
failures, warnings = 0, 0


def report(ok, label, detail="", warn=False):
    global failures, warnings
    tag = "PASS" if ok else ("WARN" if warn else "FAIL")
    if not ok and not warn:
        failures += 1
    if not ok and warn:
        warnings += 1
    print(f"[{tag}] {label} {detail}")


def main():
    try:
        store = Store()
        seeds = loader.list_seeds()
        for tenant, seed in seeds.items():
            info = loader.load_tenant(store, seed)
            report(True, f"load seed '{tenant}'", f"({info['nodes']} nodes, {info['edges']} edges)")
    except Exception as exc:
        print(f"[FAIL] cannot reach FalkorDB at {cfg.falkor_host}:{cfg.falkor_port}: {exc}")
        print("       Start it with: docker compose up -d")
        return 1

    ctx = Ctx(store, "lumen")
    checks = [
        ("entities: decisions", Q.Q_DECISIONS, None, 10),
        ("entities: systems", Q.Q_SYSTEMS, None, 10),
        ("trace: decision", Q.Q_TRACE_CORE, {"id": "d_queue"}, 1),
        ("trace: deciders", Q.Q_TRACE_DECIDERS, {"id": "d_queue"}, 2),
        ("trace: sources", Q.Q_TRACE_SOURCES, {"id": "d_queue"}, 3),
        ("trace: older (variable-length)", Q.Q_TRACE_OLDER, {"id": "d_queue"}, 2),
        ("trace: newer (variable-length)", Q.Q_TRACE_NEWER, {"id": "d_rabbit"}, 2),
        ("trace: affects", Q.Q_TRACE_AFFECTS, {"id": "d_queue"}, 3),
        ("trace: chain edges (IN list param)", Q.Q_CHAIN_EDGES, {"ids": ["d_queue", "d_pollold", "d_rabbit"]}, 2),
        ("stale: all (OPTIONAL MATCH)", Q.Q_STALE_ALL, None, 1),
        ("stale: one", Q.Q_STALE_ONE, {"id": "d_fraudvendor"}, 1),
        ("who: knows", Q.Q_KNOWS, {"id": "s_ledger"}, 3),
        ("who: worked on projects using", Q.Q_WORKED, {"id": "s_ledger"}, 1),
        ("who: decided related", Q.Q_DECIDED, {"id": "s_ledger"}, 1),
        ("who: owner", Q.Q_OWNER, {"id": "s_ledger"}, 1),
        ("impact: blast radius (min(length(path)))", Q.Q_BLAST, {"id": "s_bus"}, 5),
        ("impact: dependency edges", Q.Q_DEP_EDGES, None, 5),
        ("impact: blast edges", Q.Q_BLAST_EDGES, {"ids": ["s_bus", "s_billing", "s_notify"]}, 2),
        ("impact: owner teams", Q.Q_OWNERS_TEAMS, {"ids": ["s_bus", "s_billing"]}, 2),
        ("impact: people who know", Q.Q_OWNERS_PEOPLE, {"ids": ["s_bus", "s_billing"]}, 2),
        ("memory: playbook", Q.Q_PLAYBOOK, {"id": "pb_why"}, 1),
        ("node detail (Node object)", Q.Q_NODE, {"id": "d_queue"}, 1),
        ("neighbours out", Q.Q_NEIGH_OUT, {"id": "d_queue"}, 3),
        ("neighbours in", Q.Q_NEIGH_IN, {"id": "d_queue"}, 1),
    ]
    for name, cypher, params, minimum in checks:
        try:
            rows = ctx.q(name, cypher, params, quiet=True)
            report(len(rows) >= minimum, name, f"rows={len(rows)} (expected >= {minimum})")
        except Exception as exc:
            report(False, name, str(exc)[:160])

    for name, cypher, params in (
        ("algorithm: algo.pageRank", Q.Q_PAGERANK, None),
        ("algorithm: shortestPath", Q.Q_SHORTEST, {"a": "s_mobile", "b": "s_bus"}),
    ):
        try:
            rows = ctx.q(name, cypher, params, quiet=True)
            report(bool(rows) and rows[0][0] is not None, name, f"rows={len(rows)}", warn=True)
        except Exception as exc:
            report(False, name + " (Python fallback will be used)", str(exc)[:140], warn=True)

    # end-to-end flow, exactly like the demo
    ex = seeds["lumen"]["examples"]
    expectations = [
        (ex[0], ["[d_queue]", "[doc_adr014]", "Impact"]),
        (ex[1], ["Who to ask", "Sofia"]),
        (ex[2], ["[d_fraudvendor]"]),
        (ex[3], ["Validity: STALE"]),
        (ex[4], ["Action taken"]),
    ]
    for question, needles in expectations:
        try:
            out = agents.ask(store, "lumen", question)
            missing = [n for n in needles if n not in out["answer"]]
            report(not missing, "ask: " + question[:50], f"missing={missing}" if missing else f"{len(out['receipts'])} graph calls, {out['ms']} ms")
        except Exception as exc:
            report(False, "ask: " + question[:50], str(exc)[:160])
    try:
        res = agents.ingest(store, "lumen", seeds["lumen"]["sample_document"])
        report(res["replaced"] == "doc_adr014" and len(res["tasks"]) == 1, "ingest sample document", f"tasks={[t['decision'] for t in res['tasks']]}")
        run = agents.run_agents(store, "lumen")
        verdicts = {t["decision"]: t["verdict"] for t in run["tasks"]}
        report(verdicts.get("d_queue") == "needs_update" and verdicts.get("d_fraudvendor") == "needs_update", "agents hand-off", str(verdicts))
        snap = agents.snapshot(store, "lumen")
        report(any(n["label"] == "ChangeRequest" for n in snap["nodes"]) and any(n["label"] == "Task" for n in snap["nodes"]), "graph snapshot shows Task + ChangeRequest nodes")
    except Exception as exc:
        report(False, "ingest / agents", str(exc)[:200])

    for tenant in seeds:
        store.delete_graph(tenant)
    print()
    print(f"RESULT: {failures} failure(s), {warnings} warning(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
