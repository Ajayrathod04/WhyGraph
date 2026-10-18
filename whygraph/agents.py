"""The two cooperating agents and the tools they share.

Analyst   answers questions by running PLAYBOOKS (tool sequences stored IN THE GRAPH as procedural memory),
          writes episodic memory (Question nodes) and takes action (ChangeRequest nodes, Task nodes).
Archivist keeps knowledge current: ingests new documents, marks outdated evidence, and closes Tasks.

They never call each other directly. They hand work over through (:Task) nodes in the shared tenant graph:
    open (assignee analyst, stage assess)  ->  recheck (assignee archivist)  ->  done
"""
import datetime
import re
import time
import uuid

from . import algos, llm, nlu
from . import queries as Q
from .db import Ctx

ALLOWED_INTENTS = ["why", "who", "impact", "stale", "plan"]
DEFAULT_STEPS = {
    "why": "trace,stale_check",
    "who": "who_knows",
    "impact": "impact,pagerank",
    "stale": "stale_scan",
    "plan": "impact,pagerank,shortest_path,plan",
}
NEWLINE = "\u00b6"  # multi-line text is stored on one line in the graph and restored when read


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def enc(text):
    return (text or "").replace("\r", "").replace("\n", NEWLINE)


def dec(text):
    return (text or "").replace(NEWLINE, "\n")


def clean(text, limit):
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def slug(text, limit=36):
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:limit] or "item"


# ============================================================ entities
def load_entities(ctx):
    decisions = [
        {"id": r[0], "title": r[1], "date": r[2], "status": r[3], "rationale": r[4], "aliases": r[5] or ""}
        for r in ctx.q("entities: decisions", Q.Q_DECISIONS, quiet=True)
    ]
    systems = [
        {"id": r[0], "name": r[1], "criticality": r[2] or 0, "aliases": r[3] or ""}
        for r in ctx.q("entities: systems", Q.Q_SYSTEMS, quiet=True)
    ]
    people = [{"id": r[0], "name": r[1], "team": r[2]} for r in ctx.q("entities: people", Q.Q_PEOPLE, quiet=True)]
    docs = [
        {"id": r[0], "title": r[1], "kind": r[2], "date": r[3], "status": r[4], "url": r[5], "excerpt": r[6]}
        for r in ctx.q("entities: documents", Q.Q_DOCS, quiet=True)
    ]
    return {"decisions": decisions, "systems": systems, "people": people, "docs": docs}


class Run:
    """State of one question while its playbooks execute."""

    def __init__(self, ctx, ent, decision, system):
        self.ctx = ctx
        self.ent = ent
        self.decision = decision
        self.system = system
        self.sysmap = {s["id"]: s for s in ent["systems"]}
        self.docmap = {d["id"]: d for d in ent["docs"]}
        self.res = {}
        self.nodes = set()
        self.edges = set()
        self.notes = []
        self.changed = False
        self.done = set()

    def hl(self, *ids):
        for i in ids:
            if i:
                self.nodes.add(i)

    def hl_edge(self, a, rel, b):
        if a and b:
            self.edges.add((a, rel, b))
            self.nodes.update((a, b))


def affected_systems(run, prefer):
    """Systems in play: the decision's AFFECTS list, or the named system (order depends on the intent)."""
    if prefer == "who" and run.system:
        return [run.system["id"]]
    if run.decision:
        if "affects" not in run.res:
            rows = run.ctx.q("decision affects systems", Q.Q_TRACE_AFFECTS, {"id": run.decision["id"]})
            run.res["affects"] = [r[0] for r in rows]
        if run.res["affects"]:
            return run.res["affects"]
    return [run.system["id"]] if run.system else []


def sys_name(run, sid):
    return run.sysmap.get(sid, {}).get("name", sid)


# ============================================================ tools (each one = a few Cypher queries)
def tool_trace(run):
    d, ctx = run.decision, run.ctx
    if not d:
        run.notes.append("Tracing needs a specific decision.")
        return
    core = ctx.q("trace: decision", Q.Q_TRACE_CORE, {"id": d["id"]})
    deciders = ctx.q("trace: who decided", Q.Q_TRACE_DECIDERS, {"id": d["id"]})
    sources = ctx.q("trace: evidence documents", Q.Q_TRACE_SOURCES, {"id": d["id"]})
    older = ctx.q("trace: superseded decisions (variable-length path)", Q.Q_TRACE_OLDER, {"id": d["id"]})
    newer = ctx.q("trace: later decisions that replaced it", Q.Q_TRACE_NEWER, {"id": d["id"]})
    affects = ctx.q("trace: systems affected", Q.Q_TRACE_AFFECTS, {"id": d["id"]})
    run.res["affects"] = [r[0] for r in affects]
    ids = [d["id"]] + [r[0] for r in older] + [r[0] for r in newer]
    chain = ctx.q("trace: lineage edges", Q.Q_CHAIN_EDGES, {"ids": ids}) if len(ids) > 1 else []
    c = core[0] if core else [d["id"], d["title"], d.get("date"), d.get("status"), d.get("rationale")]
    trace = {
        "id": c[0], "title": c[1], "date": c[2], "status": c[3], "rationale": c[4],
        "deciders": [{"id": r[0], "name": r[1], "team": r[2]} for r in deciders],
        "sources": [
            {"id": r[0], "title": r[1], "kind": r[2], "date": r[3], "status": r[4], "url": r[5], "excerpt": r[6]}
            for r in sources
        ],
        "older": [{"id": r[0], "title": r[1], "date": r[2], "status": r[3]} for r in older],
        "newer": [{"id": r[0], "title": r[1], "date": r[2], "status": r[3]} for r in newer],
        "affects": [{"id": r[0], "name": r[1], "criticality": r[2]} for r in affects],
    }
    run.res["trace"] = trace
    run.hl(d["id"])
    for p in trace["deciders"]:
        run.hl_edge(p["id"], "DECIDED", d["id"])
    for s in trace["sources"]:
        run.hl_edge(d["id"], "BASED_ON", s["id"])
    for s in trace["affects"]:
        run.hl_edge(d["id"], "AFFECTS", s["id"])
    for a, b in chain:
        run.hl_edge(a, "SUPERSEDES", b)
    run.hl(*[o["id"] for o in trace["older"]], *[n["id"] for n in trace["newer"]])
    run.viewed_decision = d["id"]


def tool_stale_check(run):
    d, ctx = run.decision, run.ctx
    if not d:
        return
    rows = ctx.q("stale check: is any evidence outdated?", Q.Q_STALE_ONE, {"id": d["id"]})
    reasons = [{"doc": r[0], "doc_title": r[1], "new": r[2], "new_title": r[3]} for r in rows]
    run.res["stale_check"] = {"stale": bool(reasons), "reasons": reasons}
    for r in reasons:
        run.hl_edge(d["id"], "BASED_ON", r["doc"])
        if r["new"]:
            run.hl_edge(r["doc"], "REPLACED_BY", r["new"])


def tool_who_knows(run):
    ctx = run.ctx
    ids = affected_systems(run, "who")
    if not ids:
        run.notes.append("Tell me which system you are asking about.")
        return
    out = []
    for sid in ids[:3]:
        knows = ctx.q(f"who knows: {sys_name(run, sid)}", Q.Q_KNOWS, {"id": sid})
        worked = ctx.q(f"who worked on projects using: {sys_name(run, sid)}", Q.Q_WORKED, {"id": sid})
        decided = ctx.q(f"who decided things affecting: {sys_name(run, sid)}", Q.Q_DECIDED, {"id": sid})
        owner = ctx.q(f"owning team: {sys_name(run, sid)}", Q.Q_OWNER, {"id": sid})
        people = {}

        def person(pid, name, team):
            return people.setdefault(pid, {"id": pid, "name": name, "team": team, "score": 0, "why": [], "projects": [], "decisions": []})

        for pid, name, team in knows:
            p = person(pid, name, team)
            p["score"] += 3
            p["why"].append("knows the system")
        for pid, name, team, prid, prname in worked:
            p = person(pid, name, team)
            p["score"] += 2
            p["projects"].append((prid, prname))
        for pid, name, team, did, dtitle in decided:
            p = person(pid, name, team)
            p["score"] += 1
            p["decisions"].append((did, dtitle))
        ranked = sorted(people.values(), key=lambda x: (-x["score"], x["name"]))[:4]
        for p in ranked:
            if p["projects"]:
                p["why"].append("worked on " + ", ".join(n for _, n in p["projects"][:2]))
            if p["decisions"]:
                p["why"].append(f"made {len(p['decisions'])} related decision(s)")
        out.append(
            {"id": sid, "name": sys_name(run, sid), "owners": [{"id": r[0], "name": r[1]} for r in owner], "people": ranked}
        )
        run.hl(sid)
        for p in ranked[:3]:
            run.hl_edge(p["id"], "KNOWS", sid)
            for prid, _ in p["projects"][:1]:
                run.hl_edge(p["id"], "WORKED_ON", prid)
                run.hl_edge(prid, "USES", sid)
        for o in owner:
            run.hl_edge(o[0], "OWNS", sid)
    run.res["who"] = out
    if run.system:
        run.viewed_system = run.system["id"]


def _dep_edges(run):
    if "dep_edges" not in run.res:
        rows = run.ctx.q("read dependency edges (for fallback)", Q.Q_DEP_EDGES)
        run.res["dep_edges"] = [(r[0], r[1]) for r in rows]
    return run.res["dep_edges"]


def tool_impact(run):
    ctx = run.ctx
    roots = affected_systems(run, "impact")
    if not roots:
        run.notes.append("Name a decision or a system and I can show what depends on it.")
        return
    blast, engine = {}, "cypher"
    for rid in roots:
        try:
            rows = ctx.q(f"blast radius of {sys_name(run, rid)}", Q.Q_BLAST, {"id": rid})
            found = {r[0]: int(r[3]) for r in rows}
        except Exception:
            engine = "python-fallback"
            ctx.tick("blast radius", "python-fallback", "variable-length path unsupported here; BFS over edges read from FalkorDB")
            found = algos.blast_radius(_dep_edges(run), rid)
        for sid, hops in found.items():
            if sid in roots:
                continue
            if sid not in blast or hops < blast[sid]["hops"]:
                blast[sid] = {"id": sid, "hops": hops, "via": rid}
    items = []
    for sid, info in blast.items():
        s = run.sysmap.get(sid, {"name": sid, "criticality": 0})
        items.append({"id": sid, "name": s["name"], "criticality": s.get("criticality", 0), "hops": info["hops"], "via": info["via"]})
    items.sort(key=lambda x: (x["hops"], x["name"]))
    all_ids = list(roots) + [i["id"] for i in items]
    teams = ctx.q("owners of affected systems", Q.Q_OWNERS_TEAMS, {"ids": all_ids})
    people = ctx.q("people who know affected systems", Q.Q_OWNERS_PEOPLE, {"ids": all_ids})
    edges = ctx.q("dependency edges inside blast radius", Q.Q_BLAST_EDGES, {"ids": all_ids})
    team_map, people_map = {}, {}
    for tid, tname, sid in teams:
        team_map.setdefault(tid, {"id": tid, "name": tname, "systems": []})["systems"].append(sys_name(run, sid))
    for pid, pname, pteam, sid in people:
        people_map.setdefault(pid, {"id": pid, "name": pname, "team": pteam, "systems": []})["systems"].append(sys_name(run, sid))
    run.res["impact"] = {
        "roots": [{"id": r, "name": sys_name(run, r), "criticality": run.sysmap.get(r, {}).get("criticality", 0)} for r in roots],
        "blast": items,
        "teams": sorted(team_map.values(), key=lambda t: t["name"]),
        "people": sorted(people_map.values(), key=lambda p: (-len(p["systems"]), p["name"])),
        "engine": engine,
    }
    run.hl(*all_ids)
    for a, b in edges:
        run.hl_edge(a, "DEPENDS_ON", b)
    if run.decision:
        run.viewed_decision = run.decision["id"]
    if run.system:
        run.viewed_system = run.system["id"]


def tool_pagerank(run):
    ctx = run.ctx
    impact = run.res.get("impact")
    if not impact:
        return
    engine, scores = "cypher", {}
    try:
        rows = ctx.q("PageRank over DEPENDS_ON (graph algorithm)", Q.Q_PAGERANK)
        scores = {r[0]: float(r[1]) for r in rows}
        if not scores:
            raise ValueError("empty")
    except Exception:
        engine = "python-fallback"
        ctx.tick("PageRank", "python-fallback", "algo.pageRank unavailable; power iteration over edges read from FalkorDB")
        scores = algos.pagerank(_dep_edges(run))
    ids = [r["id"] for r in impact["roots"]] + [b["id"] for b in impact["blast"]]
    ranked = sorted(({"id": i, "name": sys_name(run, i), "score": round(scores.get(i, 0.0), 4)} for i in ids), key=lambda x: -x["score"])
    run.res["rank"] = {"items": ranked, "engine": engine}


def tool_shortest_path(run):
    ctx = run.ctx
    impact = run.res.get("impact")
    if not impact or not impact["blast"]:
        return
    scores = {r["id"]: r["score"] for r in run.res.get("rank", {}).get("items", [])}
    target = max(impact["blast"], key=lambda b: (b["criticality"], scores.get(b["id"], 0), b["hops"]))
    ids, engine = None, "cypher"
    try:
        rows = ctx.q(f"shortest dependency chain: {target['name']} to {sys_name(run, target['via'])}", Q.Q_SHORTEST, {"a": target["id"], "b": target["via"]})
        if rows and rows[0][1]:
            ids = list(rows[0][1])
        elif rows:
            ids = None
    except Exception:
        engine = "python-fallback"
        ctx.tick("shortest path", "python-fallback", "shortestPath unavailable; BFS over edges read from FalkorDB")
        ids = algos.shortest_path(_dep_edges(run), target["id"], target["via"])
    if ids:
        run.res["path"] = {"ids": ids, "names": [sys_name(run, i) for i in ids], "engine": engine, "target": target["id"]}
        for a, b in zip(ids, ids[1:]):
            run.hl_edge(a, "DEPENDS_ON", b)


def tool_stale_scan(run):
    ctx = run.ctx
    rows = ctx.q("stale scan: decisions resting on outdated evidence", Q.Q_STALE_ALL)
    items = []
    for did, dtitle, dstatus, xid, xtitle, nid, ntitle in rows:
        ctx.q(f"open hand-off task for {did}", Q.Q_TASK_OPEN, {"did": did, "tid": "t_" + did, "opener": "analyst", "now": now_iso()})
        items.append({"id": did, "title": dtitle, "status": dstatus, "doc": xid, "doc_title": xtitle, "new": nid, "new_title": ntitle, "task": "t_" + did})
        run.hl_edge(did, "BASED_ON", xid)
        if nid:
            run.hl_edge(xid, "REPLACED_BY", nid)
        run.hl_edge("t_" + did, "ABOUT", did)
    run.res["stale"] = items
    run.changed = bool(items)


def tool_decisions_for_system(run):
    if not run.system:
        return
    rows = run.ctx.q(f"decisions affecting {run.system['name']}", Q.Q_DECISIONS_FOR_SYSTEM, {"id": run.system["id"]})
    run.res["decisions_for_system"] = [{"id": r[0], "title": r[1], "date": r[2], "status": r[3]} for r in rows]
    run.hl(run.system["id"])
    for r in rows:
        run.hl_edge(r[0], "AFFECTS", run.system["id"])
    run.viewed_system = run.system["id"]


def tool_plan(run):
    """The ACTION: writes a draft ChangeRequest into the graph and links the people to notify."""
    ctx, d = run.ctx, run.decision
    if not d:
        run.notes.append("A reversal plan needs a specific decision. Name one (for example the billing queue migration).")
        return
    if "trace" not in run.res:
        tool_trace(run)
    impact = run.res.get("impact")
    if not impact:
        return
    trace = run.res["trace"]
    ranks = {r["id"]: r["score"] for r in run.res.get("rank", {}).get("items", [])}
    order = sorted(impact["blast"], key=lambda b: (-b["criticality"], -ranks.get(b["id"], 0)))
    roots = ", ".join(r["name"] for r in impact["roots"])
    lines = [
        f"# Change request: reverse \"{trace['title']}\"",
        f"Decision {trace['id']} was made on {trace['date']} by {', '.join(p['name'] for p in trace['deciders']) or 'unknown'} (status: {trace['status']}).",
        f"Rationale on record: {trace['rationale']}",
        "",
        "## Evidence to re-check",
    ]
    lines += [f"- {s['title']} ({s['kind']}, {s['date']}, {s['status']})" for s in trace["sources"]] or ["- none recorded"]
    lines += ["", f"## Blast radius ({len(impact['blast'])} downstream systems)", "| System | Hops | Criticality | PageRank |", "|---|---|---|---|"]
    lines += [f"| {b['name']} | {b['hops']} | {b['criticality']} | {ranks.get(b['id'], 0)} |" for b in order] or ["| none | | | |"]
    if "path" in run.res:
        lines += ["", "## Failure path", " -> ".join(run.res["path"]["names"]) + " (each depends on the next)"]
    lines += ["", "## Notify"]
    lines += [f"- Team {t['name']}: owns {', '.join(t['systems'])}" for t in impact["teams"]] or ["- no owning team recorded"]
    lines += [f"- {p['name']} ({p['team']}): knows {', '.join(p['systems'])}" for p in impact["people"][:6]]
    top = ", ".join(b["name"] for b in order[:3]) or "the affected systems"
    lines += [
        "", "## Steps",
        f"1. Announce a change window to the teams above and freeze other changes to {roots}.",
        "2. Re-read the evidence listed above and confirm the rationale no longer holds.",
        f"3. Prepare and rehearse the rollback for {roots}.",
        f"4. After rollback, verify in this order: {top}.",
        f"5. Record the outcome as a new Decision that SUPERSEDES {trace['id']}.",
    ]
    body = "\n".join(lines)
    cr_id = "cr_" + d["id"]
    ctx.q("ACTION: write draft change request into the graph", Q.Q_CR_UPSERT, {"did": d["id"], "id": cr_id, "title": f"Reverse: {trace['title']}"[:120], "body": enc(body), "now": now_iso()})
    notified = impact["people"][:6]
    for p in notified:
        ctx.q(f"ACTION: notify {p['name']}", Q.Q_CR_NOTIFY, {"id": cr_id, "pid": p["id"]})
    run.res["plan"] = {"id": cr_id, "title": f"Reverse: {trace['title']}", "body": body, "notified": [{"id": p["id"], "name": p["name"]} for p in notified]}
    run.hl_edge(cr_id, "PROPOSES_REVERSAL_OF", d["id"])
    for p in notified:
        run.hl_edge(cr_id, "NOTIFY", p["id"])
    run.changed = True


TOOLS = {
    "trace": tool_trace, "stale_check": tool_stale_check, "who_knows": tool_who_knows, "impact": tool_impact,
    "pagerank": tool_pagerank, "shortest_path": tool_shortest_path, "plan": tool_plan,
    "stale_scan": tool_stale_scan, "decisions_for_system": tool_decisions_for_system,
}


# ============================================================ answer composition (offline, deterministic)
def _c(i):
    return f"[{i}]"


def compose(run):
    r, parts = run.res, []
    if "trace" in r:
        t = r["trace"]
        who = " and ".join(_c(p["id"]) + " " + p["name"] for p in t["deciders"]) or "an unrecorded decider"
        parts.append(f"**Why:** {_c(t['id'])} \"{t['title']}\" was decided on {t['date']} by {who}. Rationale: {t['rationale']}")
        if t["sources"]:
            parts.append("**Evidence:** " + "; ".join(f"{_c(s['id'])} {s['title']} ({s['kind']}, {s['date']}{', OUTDATED' if s['status'] == 'outdated' else ''})" for s in t["sources"]))
        if t["affects"]:
            parts.append("**Touches:** " + ", ".join(f"{_c(s['id'])} {s['name']}" for s in t["affects"]))
        if t["older"]:
            parts.append("**Lineage:** it superseded " + "; ".join(f"{_c(o['id'])} \"{o['title']}\" ({o['date']})" for o in t["older"]))
        if t["newer"]:
            parts.append("**Later:** it was superseded by " + "; ".join(f"{_c(n['id'])} \"{n['title']}\" ({n['date']})" for n in t["newer"]))
    if "stale_check" in r:
        sc = r["stale_check"]
        if sc["stale"]:
            parts.append("**Validity: STALE.** " + " ".join(
                f"Evidence {_c(x['doc'])} \"{x['doc_title']}\" was replaced" + (f" by {_c(x['new'])} \"{x['new_title']}\"." if x["new"] else ".") for x in sc["reasons"]
            ) + " The rationale may no longer hold; ask the Archivist to re-check.")
        else:
            parts.append("**Validity:** none of its evidence is marked outdated.")
    if "decisions_for_system" in r:
        ds = r["decisions_for_system"]
        parts.append(f"**Decisions affecting {_c(run.system['id'])} {run.system['name']}:** " + ("; ".join(f"{_c(d['id'])} \"{d['title']}\" ({d['date']}, {d['status']})" for d in ds) or "none recorded"))
    if "who" in r:
        for w in r["who"]:
            own = (" Owned by team " + ", ".join(o["name"] for o in w["owners"]) + ".") if w["owners"] else ""
            people = "; ".join(f"{i}. {_c(p['id'])} {p['name']} ({p['team']}): " + ", ".join(p["why"]) for i, p in enumerate(w["people"], 1)) or "nobody recorded"
            parts.append(f"**Who to ask about {_c(w['id'])} {w['name']}:**{own} {people}.")
    if "impact" in r:
        im = r["impact"]
        roots = ", ".join(f"{_c(x['id'])} {x['name']}" for x in im["roots"])
        if im["blast"]:
            by_hop = {}
            for b in im["blast"]:
                by_hop.setdefault(b["hops"], []).append(f"{_c(b['id'])} {b['name']}")
            hops = "; ".join(f"hop {h}: {', '.join(v)}" for h, v in sorted(by_hop.items()))
            parts.append(f"**Impact:** a change to {roots} reaches {len(im['blast'])} downstream systems ({hops}).")
        else:
            parts.append(f"**Impact:** nothing else depends on {roots}.")
        if im["teams"]:
            parts.append("**Teams to notify:** " + ", ".join(f"{_c(t['id'])} {t['name']}" for t in im["teams"]))
    if "rank" in r:
        top = r["rank"]["items"][:4]
        parts.append("**Ranked by PageRank** (importance in the dependency graph): " + ", ".join(f"{_c(i['id'])} {i['name']} ({i['score']})" for i in top))
    if "path" in r:
        parts.append("**Failure path:** " + " \u2192 ".join(_c(i) + " " + n for i, n in zip(r["path"]["ids"], r["path"]["names"])) + " (each depends on the next).")
    if "plan" in r:
        p = r["plan"]
        parts.append(f"**Action taken:** wrote draft change request {_c(p['id'])} into the graph and linked {len(p['notified'])} people to notify: " + ", ".join(x["name"] for x in p["notified"]) + ". Open the Changes tab to read or download it.")
    if "stale" in r:
        items = r["stale"]
        if items:
            parts.append(f"**Stale decisions ({len(items)}):** " + "; ".join(
                f"{_c(s['id'])} \"{s['title']}\" rests on {_c(s['doc'])} which was replaced" + (f" by {_c(s['new'])}" if s["new"] else "") + f" (task {_c(s['task'])} opened for the agents)" for s in items))
        else:
            parts.append("**Stale decisions:** none. Every active decision rests on current evidence.")
    for n in run.notes:
        parts.append(n)
    return "\n\n".join(parts) if parts else "I found nothing in the graph for that."


# ============================================================ Analyst: answering questions
def _valid_route(routed, ent):
    if not isinstance(routed, dict):
        return None
    dmap = {d["id"]: d for d in ent["decisions"]}
    smap = {s["id"]: s for s in ent["systems"]}
    intents = [i for i in (routed.get("intents") or []) if i in ALLOWED_INTENTS]
    return intents, dmap.get(routed.get("decision_id")), smap.get(routed.get("system_id"))


def ask(store, tenant, question):
    started = time.perf_counter()
    question = clean(question, 500)
    if not question:
        raise ValueError("Ask a question first.")
    ctx = Ctx(store, tenant)
    ent = load_entities(ctx)
    usage = {r[0]: r[2] for r in ctx.q("episodic memory: most consulted decisions", Q.Q_FREQ, quiet=True)}
    router = "rules"
    intents, decision, system = [], None, None
    if llm.enabled():
        routed = _valid_route(llm.route(question, ent["decisions"], ent["systems"]), ent)
        if routed and (routed[0] or routed[1] or routed[2]):
            intents, decision, system = routed
            router = "llm"
    if router == "rules":
        intents = nlu.detect_intents(question)
        decision, system = nlu.resolve(question, ent["decisions"], ent["systems"], usage)
    intents, note = nlu.suggest_steps(intents, decision, system)
    run = Run(ctx, ent, decision, system)
    run.viewed_decision = None
    run.viewed_system = None
    steps_used = []
    if not intents:
        answer = note + " Try naming a decision or system, for example: " + (ent["decisions"][0]["title"] if ent["decisions"] else "a decision") + "."
        evidence = answer
    else:
        for intent in intents:
            rows = ctx.q(f"procedural memory: playbook '{intent}'", Q.Q_PLAYBOOK, {"id": "pb_" + intent})
            raw = rows[0][0] if rows and rows[0][0] else DEFAULT_STEPS[intent]
            steps = [s.strip() for s in raw.split(",") if s.strip() in TOOLS]
            if intent == "why" and not decision and system:
                steps = ["decisions_for_system"]
            steps_used.append({"intent": intent, "steps": steps})
            for step in steps:
                if step in run.done:
                    continue
                run.done.add(step)
                TOOLS[step](run)
            ctx.q(f"procedural memory: playbook '{intent}' used", Q.Q_PLAYBOOK_USE, {"id": "pb_" + intent, "now": now_iso()}, quiet=True)
        evidence = compose(run)
        answer = evidence
        if llm.enabled():
            phrased = llm.phrase(question, evidence)
            if phrased:
                answer = phrased.strip()
    qid = "q_" + str(int(time.time() * 1000)) + "_" + uuid.uuid4().hex[:5]
    ctx.q("episodic memory: remember this question", Q.Q_Q_CREATE, {"id": qid, "text": question, "intent": ",".join(intents) or "none", "ts": now_iso()})
    if getattr(run, "viewed_decision", None):
        ctx.q("episodic memory: link question to decision", Q.Q_Q_VIEWED_D, {"qid": qid, "xid": run.viewed_decision})
    if getattr(run, "viewed_system", None):
        ctx.q("episodic memory: link question to system", Q.Q_Q_VIEWED_S, {"qid": qid, "xid": run.viewed_system})
    return {
        "question": question,
        "intents": intents,
        "router": router,
        "target": {"decision": decision and {"id": decision["id"], "title": decision["title"]}, "system": system and {"id": system["id"], "name": system["name"]}},
        "answer": answer,
        "evidence": evidence,
        "phrased_by": llm.mode() if answer != evidence else "graph facts",
        "playbooks": steps_used,
        "highlight": {"nodes": sorted(run.nodes), "edges": [list(e) for e in sorted(run.edges)]},
        "receipts": ctx.receipts,
        "changed": run.changed,
        "plan": run.res.get("plan"),
        "ms": round((time.perf_counter() - started) * 1000),
    }


# ============================================================ agent hand-off loop
def list_tasks(ctx):
    return [
        {"id": r[0], "stage": r[1], "status": r[2], "assignee": r[3], "verdict": r[4], "note": r[5] or "", "created": r[6], "closed": r[7], "opened_by": r[8], "decision": r[9], "title": r[10]}
        for r in ctx.q("hand-off tasks", Q.Q_TASKS, quiet=True)
    ]


def run_agents(store, tenant):
    """One pass: Analyst opens + assesses tasks, then Archivist re-checks and closes them."""
    ctx = Ctx(store, tenant)
    ent = load_entities(ctx)
    log = []
    # ---- Analyst: make sure every stale decision has a task, then assess the ones assigned to it
    run0 = Run(ctx, ent, None, None)
    tool_stale_scan(run0)
    for t in list_tasks(ctx):
        if t["assignee"] != "analyst" or t["stage"] != "assess":
            continue
        d = next((x for x in ent["decisions"] if x["id"] == t["decision"]), None)
        run = Run(ctx, ent, d, None)
        tool_impact(run)
        tool_pagerank(run)
        im = run.res.get("impact")
        if im:
            top = run.res["rank"]["items"][0]["name"] if run.res.get("rank", {}).get("items") else "n/a"
            note = f"Analyst: {len(im['blast'])} downstream systems reached; most important by PageRank: {top}."
        else:
            note = "Analyst: no downstream impact found."
        ctx.q("Analyst hands task to Archivist", Q.Q_TASK_ASSESS, {"tid": t["id"], "note": note, "now": now_iso()}, quiet=True)
        log.append({"agent": "Analyst", "task": t["id"], "message": f"Assessed {t['title']}. {note[9:]} Handed to Archivist."})
    # ---- Archivist: re-check evidence and close
    for t in list_tasks(ctx):
        if t["assignee"] != "archivist" or t["stage"] != "recheck":
            continue
        d = next((x for x in ent["decisions"] if x["id"] == t["decision"]), None)
        rows = ctx.q("Archivist: re-read the evidence", Q.Q_STALE_ONE, {"id": t["decision"]}, quiet=True)
        if not rows:
            verdict, reason = "still_valid", "Evidence is no longer marked outdated."
            new_status = None
        else:
            old_id, old_title, new_id, new_title = rows[0]
            old_doc, new_doc = run0.docmap.get(old_id, {}), run0.docmap.get(new_id, {})
            advice = llm.verdict({"title": d["title"] if d else "", "rationale": d["rationale"] if d else ""}, {"title": old_title, "excerpt": old_doc.get("excerpt")}, {"title": new_title, "excerpt": new_doc.get("excerpt")}) if (llm.enabled() and new_id) else None
            if advice and advice.get("verdict") == "still_valid" and new_id:
                verdict, reason = "still_valid", clean(advice.get("reason", "The new document keeps the conclusion."), 200)
                ctx.q("Archivist: re-base evidence (remove old)", Q.Q_REBASE_DELETE, {"did": t["decision"], "oldid": old_id}, quiet=True)
                ctx.q("Archivist: re-base evidence (add new)", Q.Q_REBASE_ADD, {"did": t["decision"], "newid": new_id}, quiet=True)
                new_status = "active"
            else:
                verdict = "needs_update"
                reason = clean((advice or {}).get("reason", ""), 200) or (
                    f"Evidence \"{old_title}\" was replaced" + (f" by \"{new_title}\"" if new_title else "") + "; the recorded rationale cites the old document, so a human should re-validate it."
                )
                new_status = "needs_update"
        if new_status:
            ctx.q("Archivist: update decision status", Q.Q_DECISION_STATUS, {"id": t["decision"], "status": new_status}, quiet=True)
        note = clean((t["note"] + " | Archivist: " + reason), 380)
        ctx.q("Archivist closes task", Q.Q_TASK_CLOSE, {"tid": t["id"], "verdict": verdict, "note": note, "now": now_iso()}, quiet=True)
        log.append({"agent": "Archivist", "task": t["id"], "message": f"{t['title']}: {verdict.replace('_', ' ')}. {reason}"})
    if not log:
        log.append({"agent": "Analyst", "task": "", "message": "Nothing to do: no stale decisions and no open tasks."})
    return {"log": log, "tasks": list_tasks(ctx)}


# ============================================================ Archivist: ingesting a document
_KEYS = ("title", "kind", "date", "replaces", "url", "decision", "decided by", "affects", "supersedes", "rationale")


def parse_document_rules(text):
    """Offline extractor for 'Key: value' documents (see the sample in the UI)."""
    doc, decisions, current = {}, [], None
    body_lines = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^([A-Za-z ]+?)\s*:\s*(.+)$", line)
        key = m.group(1).lower() if m else None
        if m and key in _KEYS:
            value = m.group(2).strip()
            if key == "decision":
                current = {"title": value, "rationale": "", "decided_by": [], "affects": [], "supersedes": None}
                decisions.append(current)
            elif key in ("decided by", "affects", "supersedes", "rationale") and current is not None:
                if key == "rationale":
                    current["rationale"] = value
                elif key == "supersedes":
                    current["supersedes"] = value
                else:
                    current["decided_by" if key == "decided by" else "affects"] = [v.strip() for v in re.split(r",| and ", value) if v.strip()]
            else:
                doc[key] = value
        else:
            body_lines.append(line)
    if "title" not in doc and body_lines:
        doc["title"] = body_lines[0]
    doc["body"] = " ".join(body_lines)
    return doc, decisions


def match_one(value, items, name_key, alias_key=None, min_score=3):
    value = (value or "").strip()
    if not value:
        return None
    for it in items:
        if it["id"].lower() == value.lower():
            return it
    best, best_s = None, 0.0
    for it in items:
        s = nlu.score(value, it[name_key], it.get(alias_key) if alias_key else "")
        if s > best_s:
            best, best_s = it, s
    return best if best_s >= min_score else None


def normalise_rules(text, ent):
    doc, raw_decisions = parse_document_rules(text)
    ignored = []
    replaces = match_one(doc.get("replaces"), ent["docs"], "title", None, 2) if doc.get("replaces") else None
    if doc.get("replaces") and not replaces:
        ignored.append(f"replaces: {doc['replaces']}")
    out = {
        "title": clean(doc.get("title", ""), 120), "kind": clean(doc.get("kind", "Note"), 30) or "Note",
        "date": clean(doc.get("date", ""), 10), "url": clean(doc.get("url", ""), 200),
        "excerpt": clean(doc.get("body", ""), 240), "replaces": replaces["id"] if replaces else None, "decisions": [],
    }
    for rd in raw_decisions[:5]:
        deciders, affects = [], []
        for n in rd["decided_by"]:
            p = match_one(n, ent["people"], "name", None, 3)
            (deciders.append(p["id"]) if p else ignored.append(f"person: {n}"))
        for n in rd["affects"]:
            s = match_one(n, ent["systems"], "name", "aliases", 3)
            (affects.append(s["id"]) if s else ignored.append(f"system: {n}"))
        sup = match_one(rd["supersedes"], ent["decisions"], "title", "aliases", 3) if rd["supersedes"] else None
        out["decisions"].append({"title": clean(rd["title"], 140), "rationale": clean(rd["rationale"], 240), "deciders": deciders, "affects": affects, "supersedes": sup["id"] if sup else None})
    return out, ignored


def normalise_llm(raw, ent):
    ids = {k: {x["id"] for x in ent[k]} for k in ("docs", "decisions", "systems", "people")}
    ignored = []
    out = {
        "title": clean(raw.get("title", ""), 120), "kind": clean(raw.get("kind", "Note"), 30) or "Note",
        "date": clean(raw.get("date") or "", 10), "url": "", "excerpt": "",
        "replaces": raw.get("replaces_doc_id") if raw.get("replaces_doc_id") in ids["docs"] else None, "decisions": [],
    }
    for rd in (raw.get("decisions") or [])[:5]:
        deciders = [p for p in rd.get("decided_by", []) if p in ids["people"]]
        affects = [s for s in rd.get("affects", []) if s in ids["systems"]]
        if len(deciders) != len(rd.get("decided_by", [])) or len(affects) != len(rd.get("affects", [])):
            ignored.append("some ids from the model were not in the graph and were dropped")
        sup = rd.get("supersedes_decision_id")
        out["decisions"].append({"title": clean(rd.get("title", ""), 140), "rationale": clean(rd.get("rationale", ""), 240), "deciders": deciders, "affects": affects, "supersedes": sup if sup in ids["decisions"] else None})
    return out, ignored


def ingest(store, tenant, text):
    text = (text or "").strip()[:6000]
    if len(text) < 20:
        raise ValueError("Paste a document (at least a title and a line or two).")
    ctx = Ctx(store, tenant)
    ent = load_entities(ctx)
    extractor, norm, ignored = "rules", None, []
    if llm.enabled():
        raw = llm.extract(text, ent["decisions"], ent["systems"], ent["people"], ent["docs"])
        if raw:
            norm, ignored = normalise_llm(raw, ent)
            extractor = "llm"
    if norm is None:
        norm, ignored = normalise_rules(text, ent)
    if not norm["title"]:
        raise ValueError("Could not find a title. Start the document with 'Title: ...'.")
    before = {r[0] for r in ctx.q("stale before ingest", Q.Q_STALE_ALL, quiet=True)}
    doc_id = "doc_" + slug(norm["title"])
    date = norm["date"] if re.match(r"^\d{4}-\d{2}-\d{2}$", norm["date"] or "") else datetime.date.today().isoformat()
    ctx.q("Archivist: upsert document", Q.Q_DOC_UPSERT, {"id": doc_id, "title": norm["title"], "kind": norm["kind"], "date": date, "url": norm["url"] or f"https://{tenant}.example/docs/{doc_id}", "excerpt": norm["excerpt"] or norm["title"]})
    hl_nodes, hl_edges = {doc_id}, set()
    replaced = None
    if norm["replaces"] and norm["replaces"] != doc_id:
        ctx.q("Archivist: mark old document outdated + REPLACED_BY", Q.Q_DOC_REPLACE, {"oldid": norm["replaces"], "newid": doc_id})
        replaced = norm["replaces"]
        hl_edges.add((replaced, "REPLACED_BY", doc_id))
    made = []
    for nd in norm["decisions"]:
        if not nd["title"]:
            continue
        did = "d_" + slug(nd["title"])
        ctx.q("Archivist: upsert decision", Q.Q_DEC_UPSERT, {"id": did, "title": nd["title"], "date": date, "rationale": nd["rationale"] or "Recorded from a newly ingested document.", "aliases": nd["title"].lower()})
        ctx.q("Archivist: link evidence", Q.Q_DEC_BASED, {"id": did, "doc": doc_id})
        hl_nodes.add(did)
        hl_edges.add((did, "BASED_ON", doc_id))
        for sid in nd["affects"]:
            ctx.q("Archivist: link affected system", Q.Q_DEC_AFFECTS, {"id": did, "sid": sid})
            hl_edges.add((did, "AFFECTS", sid))
        for pid in nd["deciders"]:
            ctx.q("Archivist: link decider", Q.Q_DEC_DECIDER, {"id": did, "pid": pid})
            hl_edges.add((pid, "DECIDED", did))
        if nd["supersedes"] and nd["supersedes"] != did:
            ctx.q("Archivist: supersede older decision", Q.Q_DEC_SUPERSEDE, {"newid": did, "oldid": nd["supersedes"]})
            hl_edges.add((did, "SUPERSEDES", nd["supersedes"]))
        made.append({"id": did, "title": nd["title"]})
    after = ctx.q("stale after ingest", Q.Q_STALE_ALL, quiet=True)
    tasks = []
    for row in after:
        if row[0] not in before:
            ctx.q(f"Archivist opens task for {row[0]}", Q.Q_TASK_OPEN, {"did": row[0], "tid": "t_" + row[0], "opener": "archivist", "now": now_iso()})
            tasks.append({"id": "t_" + row[0], "decision": row[0], "title": row[1]})
            if row[5]:
                hl_edges.add((row[3], "REPLACED_BY", row[5]))
            hl_edges.add((row[0], "BASED_ON", row[3]))
            hl_edges.add(("t_" + row[0], "ABOUT", row[0]))
    for a, _, b in hl_edges:
        hl_nodes.update((a, b))
    return {
        "ok": True, "extractor": extractor, "document": {"id": doc_id, "title": norm["title"]}, "replaced": replaced,
        "decisions": made, "tasks": tasks, "ignored": ignored,
        "highlight": {"nodes": sorted(hl_nodes), "edges": [list(e) for e in sorted(hl_edges)]}, "receipts": ctx.receipts,
    }


# ============================================================ read models for the UI
def snapshot(store, tenant):
    ctx = Ctx(store, tenant)
    stale_ids = {r[0] for r in ctx.q("stale decisions", Q.Q_STALE_ALL, quiet=True)}
    nodes = []
    for label in Q.SNAPSHOT_LABELS:
        for row in ctx.q(f"snapshot {label}", Q.SNAP_QUERIES[label], quiet=True):
            name = row[1] or row[0]
            if label == "Task":
                name = "Task: " + str(name)[:28]
            nodes.append({"id": row[0], "label": label, "name": name, "status": row[2], "stale": label == "Decision" and row[0] in stale_ids})
    present = {n["id"] for n in nodes}
    edges = [
        {"source": r[0], "rel": r[1], "target": r[2]}
        for r in ctx.q("snapshot edges", Q.Q_SNAP_EDGES, quiet=True)
        if r[0] in present and r[2] in present
    ]
    return {"nodes": nodes, "edges": edges}


def stale_list(store, tenant):
    ctx = Ctx(store, tenant)
    return [
        {"id": r[0], "title": r[1], "status": r[2], "doc": r[3], "doc_title": r[4], "new": r[5], "new_title": r[6]}
        for r in ctx.q("stale decisions", Q.Q_STALE_ALL, quiet=True)
    ]


def memory(store, tenant):
    ctx = Ctx(store, tenant)
    return {
        "recent": [{"id": r[0], "text": r[1], "intent": r[2], "ts": r[3]} for r in ctx.q("recent", Q.Q_RECENT_Q, quiet=True)],
        "frequent": [{"id": r[0], "title": r[1], "n": r[2]} for r in ctx.q("frequent", Q.Q_FREQ, quiet=True)][:5],
        "playbooks": [{"id": r[0], "intent": r[1], "steps": r[2], "uses": r[3] or 0} for r in ctx.q("playbooks", Q.Q_PLAYBOOKS, quiet=True)],
    }


def changes(store, tenant):
    ctx = Ctx(store, tenant)
    return [
        {"id": r[0], "title": r[1], "body": dec(r[2]), "status": r[3], "created": r[4], "decision": r[5]}
        for r in ctx.q("change requests", Q.Q_CRS, quiet=True)
    ]


def node_detail(store, tenant, node_id):
    ctx = Ctx(store, tenant)
    props, label = {}, ""
    try:
        rows = ctx.q("node", Q.Q_NODE, {"id": node_id}, quiet=True)
        if rows:
            node = rows[0][0]
            props = dict(getattr(node, "properties", {}) or {})
            labels = getattr(node, "labels", []) or []
            label = labels[0] if labels else ""
    except Exception:
        pass
    for key in ("body",):
        if key in props:
            props[key] = dec(props[key])
    props.pop("seeded", None)
    out = [{"rel": r[0], "id": r[1], "name": r[2]} for r in ctx.q("neighbours out", Q.Q_NEIGH_OUT, {"id": node_id}, quiet=True)]
    inc = [{"rel": r[0], "id": r[1], "name": r[2]} for r in ctx.q("neighbours in", Q.Q_NEIGH_IN, {"id": node_id}, quiet=True)]
    return {"id": node_id, "label": label, "properties": props, "out": out, "in": inc}
