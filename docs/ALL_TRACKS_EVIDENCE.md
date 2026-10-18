# WhyGraph / RECALL — All-Tracks Evidence Matrix

> **WeMakeDevs × FalkorDB Graph Hacks 2026**  
> Primary Submission: **Track 03 — Company Brain**  
> Multi-Track Implementations: **Track 02 — Agent Memory and Coordination**, **Track 01 — Agents That Act on Connected Data**  
> Primary Database: **FalkorDB** (Docker service on `:6379`, FalkorDB Browser on `:3000`)

---

## 1. Track Evaluation Matrix

| Track | Implemented Capability | Relevant Code / API | Exact Reproducible Test Command | Expected Observable Result | Actual Latest Test Result | Honest Limitation |
|---|---|---|---|---|---|---|
| **Track 01: Agents That Act on Connected Data** | Typed graph tool registry (`trace`, `stale_check`, `who_knows`, `impact`, `pagerank`, `shortest_path`, `plan`). Tools execute real Cypher + native algorithms. | [`whygraph/agents.py`](file:///D:/whygraph/whygraph/agents.py#L115-L250)<br>[`whygraph/queries.py`](file:///D:/whygraph/whygraph/queries.py)<br>`POST /api/ask` | `.\.venv\Scripts\python.exe scripts/selfcheck.py` | Algorithm calls succeed (`algo.pageRank`, `shortestPath`), ask returns path and query receipts. | **PASS** (`algo.pageRank` 10 rows, `shortestPath` 1 row, headline ask in 20 graph calls, ~119ms). | Tool selection and execution is native Python calling parameterized Cypher over FalkorDB; an external MCP server was not implemented. |
| **Track 01: Agents That Act on Connected Data** | Safe human-in-the-loop action drafting (`ChangeRequest` node with `PROPOSES_REVERSAL_OF` and `NOTIFY` edges). | [`whygraph/agents.py`](file:///D:/whygraph/whygraph/agents.py#L320-L360)<br>[`web/impact-lab.js`](file:///D:/whygraph/web/impact-lab.js)<br>`GET /api/changes` | `.\.venv\Scripts\python.exe -m unittest tests.test_whygraph.AgentTests.test_plan_writes_change_request` | `ChangeRequest` node created in FalkorDB with affected systems and human approval badge. | **PASS** (1 test in 0.05s). Verified in Impact Lab UI with `DRAFT — HUMAN APPROVAL REQUIRED` badge. | Never mutates external production queues or deletes infrastructure; drafts are auditable graph records for human review. |
| **Track 02: Agent Memory & Coordination** | Episodic memory: every asked question persists as a `(:Question)` node with timestamp and intent, biasing future entity resolution. | [`whygraph/agents.py`](file:///D:/whygraph/whygraph/agents.py#L530-L535)<br>[`whygraph/queries.py`](file:///D:/whygraph/whygraph/queries.py) (`Q_Q_CREATE`)<br>`GET /api/memory` | `.\.venv\Scripts\python.exe -m unittest tests.test_whygraph.AgentTests.test_memory_and_procedural_use` | Question is written to graph and retrieved in recent memory list across queries. | **PASS** (1 test in 0.04s). Verified across application restarts. | Frequency-weighted resolution uses graph co-occurrence; does not implement vector embedding indexing for questions. |
| **Track 02: Agent Memory & Coordination** | Procedural memory: Playbook nodes (`:Playbook {id, intent, steps}`) stored in FalkorDB and loaded at runtime to drive tool sequences. | [`whygraph/agents.py`](file:///D:/whygraph/whygraph/agents.py#L510-L525)<br>[`whygraph/queries.py`](file:///D:/whygraph/whygraph/queries.py) (`Q_PLAYBOOK`) | `.\.venv\Scripts\python.exe -m unittest tests.test_whygraph.AgentTests.test_playbook_is_read_from_graph` | Playbook steps read from graph override default fallback steps. | **PASS** (1 test in 0.04s). `selfcheck.py` confirmed `memory: playbook rows=1`. | Dynamic playbook modification by agents during runtime is read-only; new playbooks are seeded or ingested. |
| **Track 02: Agent Memory & Coordination** | 2-Agent coordination: Analyst and Archivist communicate exclusively through `:Task` nodes (`open` → `assess` → `recheck` → `done`). | [`whygraph/agents.py`](file:///D:/whygraph/whygraph/agents.py#L560-L610)<br>`POST /api/agents/run`<br>`GET /api/tasks` | `.\.venv\Scripts\python.exe scripts/selfcheck.py` | Ingesting sample ADR flags stale decision; running agents transitions Task status to `needs_update`. | **PASS** (`agents hand-off {'d_fraudvendor': 'needs_update', 'd_queue': 'needs_update'}`). | Handoff loop is triggered per batch pass; no background socket pub/sub daemon. |
| **Track 02: Agent Memory & Coordination** | Strict multi-tenant isolation: completely separated graph databases per company (`team_lumen`, `team_orbit`). | [`whygraph/db.py`](file:///D:/whygraph/whygraph/db.py#L30-L50)<br>[`whygraph/server.py`](file:///D:/whygraph/whygraph/server.py#L62-L76) | `.\.venv\Scripts\python.exe -m unittest tests.test_whygraph.AgentTests.test_tenant_isolation_in_seed` | Querying tenant `orbit` returns only Orbit nodes; zero cross-tenant contamination with `lumen`. | **PASS** (1 test in 0.04s). Negative test confirms Lumen terms never appear in Orbit graph results. | Multi-tenancy uses FalkorDB's native multi-graph capability (`select_graph`); tenant key is validated per request. |
| **Track 03: Company Brain (Primary)** | Decision lineage: variable-length traversal (`SUPERSEDES*1..6`, `BASED_ON`, `DECIDED_BY`) tracing rationale to supporting evidence. | [`whygraph/queries.py`](file:///D:/whygraph/whygraph/queries.py#L40-L70)<br>`POST /api/ask` | `.\.venv\Scripts\python.exe scripts/selfcheck.py` | Returns deciders, source excerpts, older superseded decisions, and newer replacement decisions. | **PASS** (`trace: decision` rows=1, `sources` rows=3, `older` rows=2, `newer` rows=2). | Lineage depth limited to 6 hops to prevent unbounded traversal cycles on circular references. |
| **Track 03: Company Brain (Primary)** | Blast radius & ownership: `DEPENDS_ON*1..4` multi-hop traversal, native `algo.pageRank`, and ownership mapping (`OWNS`, `KNOWS`). | [`whygraph/queries.py`](file:///D:/whygraph/whygraph/queries.py#L110-L150)<br>[`web/impact-lab.js`](file:///D:/whygraph/web/impact-lab.js) | `.\.venv\Scripts\python.exe scripts/selfcheck.py` | Computes downstream blast radius with min path length; ranks systems by PageRank centrality; identifies accountable teams. | **PASS** (`impact: blast radius` rows=6, `dependency edges` rows=14, `algo.pageRank` rows=10). | Criticality scores are derived directly from graph centrality and declared service tiers; no fabricated machine learning scores. |
| **Track 03: Company Brain (Primary)** | Stale evidence propagation: `OPTIONAL MATCH` detecting when a supporting document is replaced or marked outdated. | [`whygraph/queries.py`](file:///D:/whygraph/whygraph/queries.py#L75-L95)<br>`GET /api/tasks` | `.\.venv\Scripts\python.exe scripts/selfcheck.py` | Automatically flags decisions that depend on superseded documents (e.g. `d_fraudvendor`). | **PASS** (`stale: all` rows=1, `stale: one` rows=1). | Conservative stale marking: requires human re-validation once evidence is superseded. |

---

## 2. Load-Bearing FalkorDB Cypher Queries

### 1. Decision Lineage & Variable-Length Path
```cypher
MATCH (d:Decision {id: $id})
OPTIONAL MATCH (d)-[:DECIDED_BY]->(p:Person)-[:MEMBER_OF]->(t:Team)
OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(doc:Document)
OPTIONAL MATCH (d)-[:SUPERSEDES*1..6]->(older:Decision)
OPTIONAL MATCH (newer:Decision)-[:SUPERSEDES*1..6]->(d)
RETURN d, collect(distinct p), collect(distinct doc), collect(distinct older), collect(distinct newer)
```

### 2. Multi-Hop Blast Radius Traversal
```cypher
MATCH path = (root:System {id: $id})<-[:DEPENDS_ON*1..4]-(dep:System)
RETURN dep.id, dep.name, dep.criticality, min(length(path)) AS hops
ORDER BY hops ASC, dep.criticality DESC
```

### 3. Native FalkorDB PageRank Centrality
```cypher
CALL algo.pageRank('System', 'DEPENDS_ON')
YIELD node, score
RETURN node.id, node.name, score
ORDER BY score DESC
```

### 4. Shortest Dependency Path
```cypher
MATCH p = shortestPath((a:System {id: $from_id})-[:DEPENDS_ON*]->(b:System {id: $to_id}))
RETURN [n in nodes(p) | n.id] AS path_nodes, length(p) AS distance
```

### 5. Stale Evidence Detection
```cypher
MATCH (d:Decision)-[:SUPPORTED_BY]->(old:Document)
WHERE old.status = 'outdated' OR old.status = 'superseded'
OPTIONAL MATCH (new:Document)-[:SUPERSEDES]->(old)
RETURN d.id, d.title, d.status, old.id, old.title, new.id, new.title
```

---

## 3. How to Reproduce All Checks Locally

```bash
# 1. Start FalkorDB
docker compose up -d

# 2. Run Self-Check (Verifies 36 queries & algorithms against live FalkorDB)
.\.venv\Scripts\python.exe scripts/selfcheck.py

# 3. Run Unit Test Suite (25 tests)
.\.venv\Scripts\python.exe -m unittest tests.test_whygraph -v

# 4. Run Syntax Validation
.\.venv\Scripts\python.exe -m compileall -q whygraph scripts tests
node --check web/app.js
node --check web/impact-lab.js

# 5. Start Application
.\.venv\Scripts\python.exe -m whygraph
```
