"""Every Cypher query WhyGraph depends on, in one place.

Read this file to understand what the product asks the graph.
Data model (labels and relationships):

  (Person)-[:MEMBER_OF]->(Team)         (Team)-[:OWNS]->(System)
  (Person)-[:WORKED_ON]->(Project)      (Project)-[:USES]->(System)
  (Person)-[:KNOWS]->(System)           (System)-[:DEPENDS_ON]->(System)
  (Person)-[:DECIDED]->(Decision)       (Decision)-[:BASED_ON]->(Document)
  (Decision)-[:AFFECTS]->(System)       (Decision)-[:SUPERSEDES]->(Decision)
  (Document)-[:REPLACED_BY]->(Document)
  Memory:  (Question)-[:VIEWED]->(Decision|System)   (Playbook {steps})
  Hand-off:(Task)-[:ABOUT]->(Decision)  Action: (ChangeRequest)-[:PROPOSES_REVERSAL_OF]->(Decision),
           (ChangeRequest)-[:NOTIFY]->(Person)

Parameters ($id, $ids ...) are always passed separately: user text is never concatenated into Cypher.
"""

# ---------------------------------------------------------------- entity lists (for resolving a question)
Q_DECISIONS = "MATCH (d:Decision) RETURN d.id, d.title, d.date, d.status, d.rationale, d.aliases ORDER BY d.date DESC"
Q_SYSTEMS = "MATCH (s:System) RETURN s.id, s.name, s.criticality, s.aliases ORDER BY s.name"
Q_PEOPLE = "MATCH (p:Person) RETURN p.id, p.name, p.team ORDER BY p.name"
Q_DOCS = "MATCH (x:Document) RETURN x.id, x.title, x.kind, x.date, x.status, x.url, x.excerpt ORDER BY x.date DESC"

# ---------------------------------------------------------------- graph snapshot for the picture
SNAPSHOT_LABELS = ["Person", "Team", "Project", "System", "Decision", "Document", "Task", "ChangeRequest"]
Q_SNAP_PERSON = "MATCH (n:Person) RETURN n.id, n.name, n.status"
Q_SNAP_TEAM = "MATCH (n:Team) RETURN n.id, n.name, n.status"
Q_SNAP_PROJECT = "MATCH (n:Project) RETURN n.id, n.name, n.status"
Q_SNAP_SYSTEM = "MATCH (n:System) RETURN n.id, n.name, n.status"
Q_SNAP_DECISION = "MATCH (n:Decision) RETURN n.id, n.title, n.status"
Q_SNAP_DOCUMENT = "MATCH (n:Document) RETURN n.id, n.title, n.status"
Q_SNAP_TASK = "MATCH (n:Task)-[:ABOUT]->(d:Decision) RETURN n.id, d.title, n.status"
Q_SNAP_CR = "MATCH (n:ChangeRequest) RETURN n.id, n.title, n.status"
SNAP_QUERIES = {
    "Person": Q_SNAP_PERSON, "Team": Q_SNAP_TEAM, "Project": Q_SNAP_PROJECT, "System": Q_SNAP_SYSTEM,
    "Decision": Q_SNAP_DECISION, "Document": Q_SNAP_DOCUMENT, "Task": Q_SNAP_TASK, "ChangeRequest": Q_SNAP_CR,
}
Q_SNAP_EDGES = "MATCH (a)-[r]->(b) RETURN a.id, type(r), b.id"

Q_COUNT = "MATCH (n) RETURN count(n)"

# ---------------------------------------------------------------- tool: trace (why was it decided?)
Q_TRACE_CORE = "MATCH (d:Decision {id:$id}) RETURN d.id, d.title, d.date, d.status, d.rationale"
Q_TRACE_DECIDERS = "MATCH (p:Person)-[:DECIDED]->(d:Decision {id:$id}) RETURN p.id, p.name, p.team"
Q_TRACE_SOURCES = (
    "MATCH (d:Decision {id:$id})-[:BASED_ON]->(x:Document) "
    "RETURN x.id, x.title, x.kind, x.date, x.status, x.url, x.excerpt"
)
Q_TRACE_OLDER = (
    "MATCH (d:Decision {id:$id})-[:SUPERSEDES*1..6]->(o:Decision) "
    "RETURN DISTINCT o.id, o.title, o.date, o.status ORDER BY o.date DESC"
)
Q_TRACE_NEWER = (
    "MATCH (n:Decision)-[:SUPERSEDES*1..6]->(d:Decision {id:$id}) "
    "RETURN DISTINCT n.id, n.title, n.date, n.status ORDER BY n.date DESC"
)
Q_TRACE_AFFECTS = "MATCH (d:Decision {id:$id})-[:AFFECTS]->(s:System) RETURN s.id, s.name, s.criticality"
Q_CHAIN_EDGES = (
    "MATCH (a:Decision)-[:SUPERSEDES]->(b:Decision) WHERE a.id IN $ids AND b.id IN $ids RETURN a.id, b.id"
)

# ---------------------------------------------------------------- tool: stale (is the evidence still valid?)
Q_STALE_ALL = (
    "MATCH (d:Decision)-[:BASED_ON]->(x:Document {status:'outdated'}) "
    "WHERE d.status = 'active' OR d.status = 'needs_update' "
    "OPTIONAL MATCH (x)-[:REPLACED_BY]->(n:Document) "
    "RETURN d.id, d.title, d.status, x.id, x.title, n.id, n.title"
)
Q_STALE_ONE = (
    "MATCH (d:Decision {id:$id})-[:BASED_ON]->(x:Document {status:'outdated'}) "
    "OPTIONAL MATCH (x)-[:REPLACED_BY]->(n:Document) "
    "RETURN x.id, x.title, n.id, n.title"
)

# ---------------------------------------------------------------- tool: who knows
Q_KNOWS = "MATCH (p:Person)-[:KNOWS]->(s:System {id:$id}) RETURN p.id, p.name, p.team"
Q_WORKED = (
    "MATCH (p:Person)-[:WORKED_ON]->(pr:Project)-[:USES]->(s:System {id:$id}) "
    "RETURN p.id, p.name, p.team, pr.id, pr.name"
)
Q_DECIDED = (
    "MATCH (p:Person)-[:DECIDED]->(d:Decision)-[:AFFECTS]->(s:System {id:$id}) "
    "RETURN p.id, p.name, p.team, d.id, d.title"
)
Q_OWNER = "MATCH (t:Team)-[:OWNS]->(s:System {id:$id}) RETURN t.id, t.name"
Q_DECISIONS_FOR_SYSTEM = (
    "MATCH (d:Decision)-[:AFFECTS]->(s:System {id:$id}) RETURN d.id, d.title, d.date, d.status ORDER BY d.date DESC"
)

# ---------------------------------------------------------------- tool: impact / blast radius + graph algorithms
Q_BLAST = (
    "MATCH path = (s:System {id:$id})<-[:DEPENDS_ON*1..4]-(t:System) "
    "RETURN t.id, t.name, t.criticality, min(length(path)) AS hops ORDER BY hops, t.name"
)
Q_DEP_EDGES = "MATCH (a:System)-[:DEPENDS_ON]->(b:System) RETURN a.id, b.id"
Q_BLAST_EDGES = (
    "MATCH (a:System)-[:DEPENDS_ON]->(b:System) WHERE a.id IN $ids AND b.id IN $ids RETURN a.id, b.id"
)
Q_OWNERS_TEAMS = "MATCH (t:Team)-[:OWNS]->(s:System) WHERE s.id IN $ids RETURN t.id, t.name, s.id"
Q_OWNERS_PEOPLE = (
    "MATCH (p:Person)-[:KNOWS]->(s:System) WHERE s.id IN $ids RETURN p.id, p.name, p.team, s.id"
)
# FalkorDB graph algorithms (see docs.falkordb.com/algorithms)
Q_PAGERANK = (
    "CALL algo.pageRank('System', 'DEPENDS_ON') YIELD node, score RETURN node.id, score ORDER BY score DESC"
)
Q_SHORTEST = (
    "MATCH (a:System {id:$a}), (b:System {id:$b}) "
    "WITH shortestPath((a)-[:DEPENDS_ON*]->(b)) AS p "
    "RETURN length(p), [n IN nodes(p) | n.id]"
)

# ---------------------------------------------------------------- hand-off tasks between the two agents
Q_TASK_OPEN = (
    "MATCH (d:Decision {id:$did}) "
    "MERGE (t:Task {id:$tid}) "
    "ON CREATE SET t.type = 'recheck', t.stage = 'assess', t.status = 'open', t.assignee = 'analyst', "
    "t.opened_by = $opener, t.created = $now, t.note = '' "
    "MERGE (t)-[:ABOUT]->(d) "
    "RETURN t.status, t.stage"
)
Q_TASKS = (
    "MATCH (t:Task)-[:ABOUT]->(d:Decision) "
    "RETURN t.id, t.stage, t.status, t.assignee, t.verdict, t.note, t.created, t.closed, t.opened_by, d.id, d.title "
    "ORDER BY t.created DESC"
)
Q_TASK_ASSESS = (
    "MATCH (t:Task {id:$tid}) "
    "SET t.stage = 'recheck', t.assignee = 'archivist', t.note = $note, t.assessed = $now"
)
Q_TASK_CLOSE = (
    "MATCH (t:Task {id:$tid}) "
    "SET t.stage = 'done', t.status = 'done', t.assignee = 'none', t.verdict = $verdict, t.note = $note, t.closed = $now"
)
Q_DECISION_STATUS = "MATCH (d:Decision {id:$id}) SET d.status = $status"
Q_REBASE_DELETE = "MATCH (d:Decision {id:$did})-[r:BASED_ON]->(o:Document {id:$oldid}) DELETE r"
Q_REBASE_ADD = "MATCH (d:Decision {id:$did}), (n:Document {id:$newid}) MERGE (d)-[:BASED_ON]->(n)"

# ---------------------------------------------------------------- memory: episodic (questions) and procedural (playbooks)
Q_Q_CREATE = "CREATE (:Question {id:$id, text:$text, intent:$intent, ts:$ts})"
Q_Q_VIEWED_D = "MATCH (q:Question {id:$qid}), (x:Decision {id:$xid}) MERGE (q)-[:VIEWED]->(x)"
Q_Q_VIEWED_S = "MATCH (q:Question {id:$qid}), (x:System {id:$xid}) MERGE (q)-[:VIEWED]->(x)"
Q_RECENT_Q = "MATCH (q:Question) RETURN q.id, q.text, q.intent, q.ts ORDER BY q.ts DESC LIMIT 8"
Q_FREQ = (
    "MATCH (q:Question)-[:VIEWED]->(d:Decision) RETURN d.id, d.title, count(q) AS n ORDER BY n DESC LIMIT 50"
)
Q_PLAYBOOK = "MATCH (p:Playbook {id:$id}) RETURN p.steps, p.uses"
Q_PLAYBOOKS = "MATCH (p:Playbook) RETURN p.id, p.title, p.steps, p.uses ORDER BY p.id"
Q_PLAYBOOK_USE = "MATCH (p:Playbook {id:$id}) SET p.uses = p.uses + 1, p.last_used = $now RETURN p.uses"

# ---------------------------------------------------------------- action: change request written back into the graph
Q_CR_UPSERT = (
    "MATCH (d:Decision {id:$did}) "
    "MERGE (c:ChangeRequest {id:$id}) "
    "SET c.title = $title, c.body = $body, c.status = 'draft', c.created = $now "
    "MERGE (c)-[:PROPOSES_REVERSAL_OF]->(d) "
    "RETURN c.id"
)
Q_CR_NOTIFY = "MATCH (c:ChangeRequest {id:$id}), (p:Person {id:$pid}) MERGE (c)-[:NOTIFY]->(p)"
Q_CRS = (
    "MATCH (c:ChangeRequest)-[:PROPOSES_REVERSAL_OF]->(d:Decision) "
    "RETURN c.id, c.title, c.body, c.status, c.created, d.id ORDER BY c.created DESC"
)

# ---------------------------------------------------------------- archivist: ingesting a new document
Q_DOC_UPSERT = (
    "MERGE (x:Document {id:$id}) "
    "SET x.title = $title, x.kind = $kind, x.date = $date, x.url = $url, x.excerpt = $excerpt, x.status = 'current'"
)
Q_DOC_REPLACE = (
    "MATCH (o:Document {id:$oldid}), (n:Document {id:$newid}) "
    "SET o.status = 'outdated' MERGE (o)-[:REPLACED_BY]->(n)"
)
Q_DEC_UPSERT = (
    "MERGE (d:Decision {id:$id}) "
    "SET d.title = $title, d.date = $date, d.rationale = $rationale, d.status = 'active', d.aliases = $aliases"
)
Q_DEC_BASED = "MATCH (d:Decision {id:$id}), (x:Document {id:$doc}) MERGE (d)-[:BASED_ON]->(x)"
Q_DEC_AFFECTS = "MATCH (d:Decision {id:$id}), (s:System {id:$sid}) MERGE (d)-[:AFFECTS]->(s)"
Q_DEC_DECIDER = "MATCH (p:Person {id:$pid}), (d:Decision {id:$id}) MERGE (p)-[:DECIDED]->(d)"
Q_DEC_SUPERSEDE = (
    "MATCH (n:Decision {id:$newid}), (o:Decision {id:$oldid}) SET o.status = 'superseded' MERGE (n)-[:SUPERSEDES]->(o)"
)

# ---------------------------------------------------------------- node detail panel
Q_NODE = "MATCH (n {id:$id}) RETURN n"
Q_NEIGH_OUT = "MATCH (n {id:$id})-[r]->(m) RETURN type(r), m.id, coalesce(m.name, m.title)"
Q_NEIGH_IN = "MATCH (m)-[r]->(n {id:$id}) RETURN type(r), m.id, coalesce(m.name, m.title)"
