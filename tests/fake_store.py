"""TEST-ONLY in-memory stand-in for the Store, so the Python glue (routing, ranking, hand-off, ingest, UI API)
can be unit-tested without a FalkorDB server. It answers the exact query strings in whygraph.queries.

The shipped product has NO such fallback: without FalkorDB the app refuses to start.
Real Cypher is verified separately by scripts/selfcheck.py against a live FalkorDB.
"""
import copy

from whygraph import algos
from whygraph import queries as Q


class FakeNode:
    def __init__(self, label, props):
        self.labels = [label]
        self.properties = props


class FakeStore:
    def __init__(self, seed, fail_algos=False):
        self.nodes, self.edges = {}, set()
        self.fail_algos = fail_algos
        self.log = []
        for label, items in copy.deepcopy(seed["nodes"]).items():
            for n in items:
                self.nodes[n["id"]] = {"label": label, **n}
        for a, rel, b in seed["edges"]:
            self.edges.add((a, rel, b))
        self.h = {
            Q.Q_DECISIONS: self.decisions, Q.Q_SYSTEMS: self.systems, Q.Q_PEOPLE: self.people, Q.Q_DOCS: self.docs,
            Q.Q_SNAP_EDGES: lambda p: [[a, r, b] for a, r, b in sorted(self.edges)],
            Q.Q_COUNT: lambda p: [[len(self.nodes)]],
            Q.Q_TRACE_CORE: self.trace_core, Q.Q_TRACE_DECIDERS: self.trace_deciders, Q.Q_TRACE_SOURCES: self.trace_sources,
            Q.Q_TRACE_OLDER: self.trace_older, Q.Q_TRACE_NEWER: self.trace_newer, Q.Q_TRACE_AFFECTS: self.trace_affects,
            Q.Q_CHAIN_EDGES: self.chain_edges, Q.Q_STALE_ALL: self.stale_all, Q.Q_STALE_ONE: self.stale_one,
            Q.Q_KNOWS: self.knows, Q.Q_WORKED: self.worked, Q.Q_DECIDED: self.decided, Q.Q_OWNER: self.owner,
            Q.Q_DECISIONS_FOR_SYSTEM: self.decisions_for_system, Q.Q_BLAST: self.blast, Q.Q_DEP_EDGES: self.dep_edges,
            Q.Q_BLAST_EDGES: self.blast_edges, Q.Q_OWNERS_TEAMS: self.owners_teams, Q.Q_OWNERS_PEOPLE: self.owners_people,
            Q.Q_PAGERANK: self.pagerank, Q.Q_SHORTEST: self.shortest,
            Q.Q_TASK_OPEN: self.task_open, Q.Q_TASKS: self.tasks, Q.Q_TASK_ASSESS: self.task_assess, Q.Q_TASK_CLOSE: self.task_close,
            Q.Q_DECISION_STATUS: self.decision_status, Q.Q_REBASE_DELETE: self.rebase_delete, Q.Q_REBASE_ADD: self.rebase_add,
            Q.Q_Q_CREATE: self.q_create, Q.Q_Q_VIEWED_D: self.q_viewed, Q.Q_Q_VIEWED_S: self.q_viewed,
            Q.Q_RECENT_Q: self.recent_q, Q.Q_FREQ: self.freq, Q.Q_PLAYBOOK: self.playbook, Q.Q_PLAYBOOKS: self.playbooks,
            Q.Q_PLAYBOOK_USE: self.playbook_use, Q.Q_CR_UPSERT: self.cr_upsert, Q.Q_CR_NOTIFY: self.cr_notify, Q.Q_CRS: self.crs,
            Q.Q_DOC_UPSERT: self.doc_upsert, Q.Q_DOC_REPLACE: self.doc_replace, Q.Q_DEC_UPSERT: self.dec_upsert,
            Q.Q_DEC_BASED: lambda p: self.add(p["id"], "BASED_ON", p["doc"]), Q.Q_DEC_AFFECTS: lambda p: self.add(p["id"], "AFFECTS", p["sid"]),
            Q.Q_DEC_DECIDER: lambda p: self.add(p["pid"], "DECIDED", p["id"]), Q.Q_DEC_SUPERSEDE: self.dec_supersede,
            Q.Q_NODE: self.node, Q.Q_NEIGH_OUT: self.neigh_out, Q.Q_NEIGH_IN: self.neigh_in,
        }
        for label, cypher in Q.SNAP_QUERIES.items():
            self.h[cypher] = (lambda lab: (lambda p: self.snap(lab)))(label)

    # --- store interface
    def run(self, tenant, name, cypher, params=None, receipts=None):
        if cypher not in self.h:
            raise AssertionError("FakeStore has no handler for: " + cypher)
        self.log.append(name)
        rows = self.h[cypher](params or {})
        if receipts is not None:
            receipts.append({"name": name, "cypher": cypher, "params": params or {}, "rows": len(rows), "ms": 0})
        return rows

    def delete_graph(self, tenant):
        pass

    # --- helpers
    def of(self, label):
        return [n for n in self.nodes.values() if n["label"] == label]

    def add(self, a, rel, b):
        self.edges.add((a, rel, b))
        return []

    def out(self, a, rel):
        return [b for (x, r, b) in sorted(self.edges) if x == a and r == rel]

    def inc(self, b, rel):
        return [a for (a, r, y) in sorted(self.edges) if y == b and r == rel]

    # --- handlers
    def decisions(self, p):
        return [[d["id"], d["title"], d["date"], d["status"], d["rationale"], d.get("aliases")] for d in sorted(self.of("Decision"), key=lambda d: d["date"], reverse=True)]

    def systems(self, p):
        return [[s["id"], s["name"], s["criticality"], s.get("aliases")] for s in sorted(self.of("System"), key=lambda s: s["name"])]

    def people(self, p):
        return [[x["id"], x["name"], x["team"]] for x in sorted(self.of("Person"), key=lambda s: s["name"])]

    def docs(self, p):
        return [[d["id"], d["title"], d["kind"], d["date"], d["status"], d["url"], d["excerpt"]] for d in sorted(self.of("Document"), key=lambda d: d["date"], reverse=True)]

    def snap(self, label):
        if label == "Task":
            return [[t["id"], self.nodes[self.out(t["id"], "ABOUT")[0]]["title"], t["status"]] for t in self.of("Task") if self.out(t["id"], "ABOUT")]
        return [[n["id"], n.get("name") or n.get("title"), n.get("status")] for n in self.of(label)]

    def trace_core(self, p):
        d = self.nodes[p["id"]]
        return [[d["id"], d["title"], d["date"], d["status"], d["rationale"]]]

    def trace_deciders(self, p):
        return [[x, self.nodes[x]["name"], self.nodes[x]["team"]] for x in self.inc(p["id"], "DECIDED")]

    def trace_sources(self, p):
        return [[x, self.nodes[x]["title"], self.nodes[x]["kind"], self.nodes[x]["date"], self.nodes[x]["status"], self.nodes[x]["url"], self.nodes[x]["excerpt"]] for x in self.out(p["id"], "BASED_ON")]

    def _walk(self, start, forward):
        seen, frontier = [], [start]
        while frontier:
            cur = frontier.pop()
            nxt = self.out(cur, "SUPERSEDES") if forward else self.inc(cur, "SUPERSEDES")
            for n in nxt:
                if n not in seen:
                    seen.append(n)
                    frontier.append(n)
        return seen

    def trace_older(self, p):
        return [[x, self.nodes[x]["title"], self.nodes[x]["date"], self.nodes[x]["status"]] for x in sorted(self._walk(p["id"], True), key=lambda i: self.nodes[i]["date"], reverse=True)]

    def trace_newer(self, p):
        return [[x, self.nodes[x]["title"], self.nodes[x]["date"], self.nodes[x]["status"]] for x in sorted(self._walk(p["id"], False), key=lambda i: self.nodes[i]["date"], reverse=True)]

    def trace_affects(self, p):
        return [[x, self.nodes[x]["name"], self.nodes[x]["criticality"]] for x in self.out(p["id"], "AFFECTS")]

    def chain_edges(self, p):
        return [[a, b] for (a, r, b) in sorted(self.edges) if r == "SUPERSEDES" and a in p["ids"] and b in p["ids"]]

    def stale_all(self, p):
        rows = []
        for d in self.of("Decision"):
            if d["status"] not in ("active", "needs_update"):
                continue
            for x in self.out(d["id"], "BASED_ON"):
                if self.nodes[x]["status"] == "outdated":
                    new = (self.out(x, "REPLACED_BY") or [None])[0]
                    rows.append([d["id"], d["title"], d["status"], x, self.nodes[x]["title"], new, new and self.nodes[new]["title"]])
        return rows

    def stale_one(self, p):
        return [[r[3], r[4], r[5], r[6]] for r in self.stale_all({}) if r[0] == p["id"]]

    def knows(self, p):
        return [[x, self.nodes[x]["name"], self.nodes[x]["team"]] for x in self.inc(p["id"], "KNOWS")]

    def worked(self, p):
        rows = []
        for pr in self.inc(p["id"], "USES"):
            for person in self.inc(pr, "WORKED_ON"):
                rows.append([person, self.nodes[person]["name"], self.nodes[person]["team"], pr, self.nodes[pr]["name"]])
        return rows

    def decided(self, p):
        rows = []
        for d in self.inc(p["id"], "AFFECTS"):
            for person in self.inc(d, "DECIDED"):
                rows.append([person, self.nodes[person]["name"], self.nodes[person]["team"], d, self.nodes[d]["title"]])
        return rows

    def owner(self, p):
        return [[x, self.nodes[x]["name"]] for x in self.inc(p["id"], "OWNS")]

    def decisions_for_system(self, p):
        return [[d, self.nodes[d]["title"], self.nodes[d]["date"], self.nodes[d]["status"]] for d in self.inc(p["id"], "AFFECTS")]

    def dep_edges(self, p):
        return [[a, b] for (a, r, b) in sorted(self.edges) if r == "DEPENDS_ON"]

    def blast(self, p):
        if self.fail_algos:
            raise RuntimeError("variable-length unsupported (simulated)")
        found = algos.blast_radius([tuple(e) for e in self.dep_edges({})], p["id"])
        return [[s, self.nodes[s]["name"], self.nodes[s]["criticality"], h] for s, h in sorted(found.items(), key=lambda kv: (kv[1], self.nodes[kv[0]]["name"]))]

    def blast_edges(self, p):
        return [e for e in self.dep_edges({}) if e[0] in p["ids"] and e[1] in p["ids"]]

    def owners_teams(self, p):
        return [[t, self.nodes[t]["name"], s] for (t, r, s) in sorted(self.edges) if r == "OWNS" and s in p["ids"]]

    def owners_people(self, p):
        return [[x, self.nodes[x]["name"], self.nodes[x]["team"], s] for (x, r, s) in sorted(self.edges) if r == "KNOWS" and s in p["ids"]]

    def pagerank(self, p):
        if self.fail_algos:
            raise RuntimeError("algo.pageRank unsupported (simulated)")
        scores = algos.pagerank([tuple(e) for e in self.dep_edges({})])
        return [[k, v] for k, v in sorted(scores.items(), key=lambda kv: -kv[1])]

    def shortest(self, p):
        if self.fail_algos:
            raise RuntimeError("shortestPath unsupported (simulated)")
        path = algos.shortest_path([tuple(e) for e in self.dep_edges({})], p["a"], p["b"])
        return [[len(path) - 1, path]] if path else [[None, None]]

    def task_open(self, p):
        if p["tid"] not in self.nodes:
            self.nodes[p["tid"]] = {"label": "Task", "id": p["tid"], "type": "recheck", "stage": "assess", "status": "open", "assignee": "analyst", "opened_by": p["opener"], "created": p["now"], "note": ""}
        self.add(p["tid"], "ABOUT", p["did"])
        t = self.nodes[p["tid"]]
        return [[t["status"], t["stage"]]]

    def tasks(self, p):
        rows = []
        for t in self.of("Task"):
            d = self.out(t["id"], "ABOUT")[0]
            rows.append([t["id"], t.get("stage"), t.get("status"), t.get("assignee"), t.get("verdict"), t.get("note"), t.get("created"), t.get("closed"), t.get("opened_by"), d, self.nodes[d]["title"]])
        return rows

    def task_assess(self, p):
        self.nodes[p["tid"]].update(stage="recheck", assignee="archivist", note=p["note"])
        return []

    def task_close(self, p):
        self.nodes[p["tid"]].update(stage="done", status="done", assignee="none", verdict=p["verdict"], note=p["note"], closed=p["now"])
        return []

    def decision_status(self, p):
        self.nodes[p["id"]]["status"] = p["status"]
        return []

    def rebase_delete(self, p):
        self.edges.discard((p["did"], "BASED_ON", p["oldid"]))
        return []

    def rebase_add(self, p):
        return self.add(p["did"], "BASED_ON", p["newid"])

    def q_create(self, p):
        self.nodes[p["id"]] = {"label": "Question", "id": p["id"], "text": p["text"], "intent": p["intent"], "ts": p["ts"]}
        return []

    def q_viewed(self, p):
        return self.add(p["qid"], "VIEWED", p["xid"])

    def recent_q(self, p):
        return [[q["id"], q["text"], q["intent"], q["ts"]] for q in sorted(self.of("Question"), key=lambda q: q["ts"], reverse=True)][:8]

    def freq(self, p):
        counts = {}
        for (q, r, d) in self.edges:
            if r == "VIEWED" and self.nodes[d]["label"] == "Decision":
                counts[d] = counts.get(d, 0) + 1
        return [[d, self.nodes[d]["title"], n] for d, n in sorted(counts.items(), key=lambda kv: -kv[1])]

    def playbook(self, p):
        pb = self.nodes.get(p["id"])
        return [[pb["steps"], pb["uses"]]] if pb else []

    def playbooks(self, p):
        return [[b["id"], b["title"], b["steps"], b["uses"]] for b in sorted(self.of("Playbook"), key=lambda b: b["id"])]

    def playbook_use(self, p):
        self.nodes[p["id"]]["uses"] += 1
        return [[self.nodes[p["id"]]["uses"]]]

    def cr_upsert(self, p):
        self.nodes[p["id"]] = {"label": "ChangeRequest", "id": p["id"], "title": p["title"], "body": p["body"], "status": "draft", "created": p["now"]}
        self.add(p["id"], "PROPOSES_REVERSAL_OF", p["did"])
        return [[p["id"]]]

    def cr_notify(self, p):
        return self.add(p["id"], "NOTIFY", p["pid"])

    def crs(self, p):
        return [[c["id"], c["title"], c["body"], c["status"], c["created"], self.out(c["id"], "PROPOSES_REVERSAL_OF")[0]] for c in self.of("ChangeRequest")]

    def doc_upsert(self, p):
        self.nodes[p["id"]] = {"label": "Document", "id": p["id"], "title": p["title"], "kind": p["kind"], "date": p["date"], "url": p["url"], "excerpt": p["excerpt"], "status": "current"}
        return []

    def doc_replace(self, p):
        self.nodes[p["oldid"]]["status"] = "outdated"
        return self.add(p["oldid"], "REPLACED_BY", p["newid"])

    def dec_upsert(self, p):
        self.nodes[p["id"]] = {"label": "Decision", "id": p["id"], "title": p["title"], "date": p["date"], "rationale": p["rationale"], "status": "active", "aliases": p["aliases"]}
        return []

    def dec_supersede(self, p):
        self.nodes[p["oldid"]]["status"] = "superseded"
        return self.add(p["newid"], "SUPERSEDES", p["oldid"])

    def node(self, p):
        n = self.nodes[p["id"]]
        return [[FakeNode(n["label"], {k: v for k, v in n.items() if k != "label"})]]

    def neigh_out(self, p):
        return [[r, b, self.nodes[b].get("name") or self.nodes[b].get("title")] for (a, r, b) in sorted(self.edges) if a == p["id"]]

    def neigh_in(self, p):
        return [[r, a, self.nodes[a].get("name") or self.nodes[a].get("title")] for (a, r, b) in sorted(self.edges) if b == p["id"]]
