# EXPLAIN.md: understand every part (hackathon rule 12)

The rules say you must be able to explain the graph model, the queries, the architecture and the technical decisions. Read this once, then open the files named in each section and click through the app while reading.

## 1. The one-paragraph story

Companies lose the *why* behind decisions. WhyGraph stores decisions, their evidence documents, the people who made them, the systems they touch and how systems depend on each other, as a graph in FalkorDB. A question is turned into a small **plan** (a playbook of tools). Each tool is a few Cypher queries. The results are stitched into an answer, and the exact queries are shown as a receipt.

## 2. The graph model (see the top of `whygraph/queries.py`)

- **Semantic memory** (company knowledge): `Person, Team, Project, System, Decision, Document`.
- **Episodic memory**: `(:Question)-[:VIEWED]->(:Decision|:System)`, one node per question asked.
- **Procedural memory**: `(:Playbook {id:'pb_why', steps:'trace,stale_check'})`. The Analyst reads `steps` at runtime, so editing the node changes behaviour (try it in FalkorDB Browser).
- **Coordination**: `(:Task)-[:ABOUT]->(:Decision)` with `stage` (`assess`, `recheck`, `done`) and `assignee` (`analyst`, `archivist`, `none`).
- **Action**: `(:ChangeRequest)-[:PROPOSES_REVERSAL_OF]->(:Decision)` and `-[:NOTIFY]->(:Person)`.
- **Tenancy**: one graph per team (`team_lumen`, `team_orbit`), chosen with `select_graph(prefix + tenant)` in `whygraph/db.py`.

## 3. The queries, in plain words

| Constant in `queries.py` | What it asks |
|---|---|
| `Q_TRACE_OLDER` `(d)-[:SUPERSEDES*1..6]->(o)` | every older decision this one replaced, up to 6 hops (variable-length path) |
| `Q_TRACE_SOURCES` | the documents the decision is based on |
| `Q_STALE_ALL` | decisions whose evidence document is `outdated`, plus what replaced it (`OPTIONAL MATCH`) |
| `Q_BLAST` `(s)<-[:DEPENDS_ON*1..4]-(t)` with `min(length(path))` | all systems that depend on `s`, with the shortest hop count |
| `Q_PAGERANK` `algo.pageRank('System','DEPENDS_ON')` | importance of each system in the dependency graph (systems many others depend on score high) |
| `Q_SHORTEST` `shortestPath(...)` | the shortest dependency chain from a critical system to the changed one |
| `Q_KNOWS`, `Q_WORKED`, `Q_DECIDED`, `Q_OWNER` | four different reasons a person is relevant to a system; Python combines them into a ranking (3 points knows, 2 per project, 1 per related decision) |
| `Q_TASK_OPEN` with `MERGE ... ON CREATE SET` | create the hand-off task once, never duplicate it |
| `Q_CR_UPSERT`, `Q_CR_NOTIFY` | the action: write the change request and link who to notify |

Direction matters: `(a)-[:DEPENDS_ON]->(b)` means *a depends on b*. So the blast radius of `b` follows the arrow **backwards**, and PageRank over `DEPENDS_ON` gives high scores to foundations that many things rely on.

## 4. The request path (`whygraph/agents.py: ask()`)

1. Load entity lists (decisions, systems, people, documents) with 4 quiet queries.
2. `nlu.detect_intents()` finds *why / who / impact / stale / plan* by keywords, in order of appearance. `nlu.resolve()` picks the decision and system by alias phrases and token overlap, with a small boost for decisions asked about before (episodic memory). If `LLM_API_KEY` is set, `llm.route()` is tried first and its ids are validated.
3. For each intent, read the playbook node, run its tools, bump `uses` on the playbook.
4. `compose()` builds the answer from structured results. Every entity appears as `[id]`, which the UI turns into a clickable chip.
5. Optionally `llm.phrase()` rewrites the facts; the original facts stay available under "Graph facts".
6. Write the `Question` node and `VIEWED` edges (episodic memory) and return the answer, highlight set and receipts.

## 5. The two agents and the hand-off

`run_agents()`:
- **Analyst**: runs the stale scan (opens a `Task` per stale decision, once), then for each task in stage `assess` computes the blast radius and PageRank and hands the task over (`assignee='archivist'`, `stage='recheck'`).
- **Archivist**: for each task in stage `recheck` re-reads the evidence. Offline it always answers `needs_update` when evidence was replaced (a human must re-validate). With an LLM it may answer `still_valid`; then it re-bases the decision onto the new document (`DELETE` old `BASED_ON`, `MERGE` new) and sets the task to `done`.

`ingest()` is the Archivist's other job: parse a document, resolve names to existing ids (unknown names are ignored and reported), write the new `Document`/`Decision` nodes and edges, mark the replaced document `outdated`, and open tasks for newly stale decisions.

## 6. Decisions you can defend

- **Why FalkorDB multi-graph for tenants?** Isolation without running separate databases; the event page highlights this capability.
- **Why stdlib HTTP server?** One dependency (`falkordb`), so a beginner can run it anywhere and judges can read all server code in one file.
- **Why an offline mode?** The demo must never depend on a network call. The LLM only phrases or routes; it cannot invent graph facts because answers are composed from query results and shown beside the facts.
- **Why Python fallbacks for algorithms?** Syntax for algorithms can vary across FalkorDB versions. If a call is rejected, edges are read from FalkorDB and the same algorithm runs in Python; the receipt says `[python-fallback]`. Tests prove both paths.
- **Why store multi-line text with a pilcrow?** Newlines inside query parameters are risky across clients, so change-request bodies are stored on one line and restored when read.

## 7. Questions a judge might ask

1. *Show me that the graph is essential.* Stop FalkorDB: at start the app prints an error and exits, and while running every API call fails. Every tool is a Cypher query in `queries.py`.
2. *How do you stop prompt injection through documents?* Documents are data. LLM output is JSON-validated against existing ids and goes into parameters only. Offline mode needs no LLM at all.
3. *What is procedural memory here?* `Playbook` nodes. Change `pb_why.steps` in FalkorDB Browser to `trace` and the stale check disappears from answers.
4. *How do the agents coordinate?* Only through `Task` nodes; no direct calls.
5. *What happens to tenants?* Separate graphs; asking in Orbit never touches Lumen.
6. *What did you not build?* Real connectors (Slack, Jira), authentication, and large-scale data. The model supports them; the demo uses synthetic data.

## 8. Make it yours (do some of these; it also shows meaningful contribution)

- Replace a seed company with your own *synthetic* story (edit `scripts/make_seed.py`, run it, restart).
- Add a new tool, for example "owners with no backup" (people who are the only `KNOWS` for a system): write the query in `queries.py`, a `tool_*` function in `agents.py`, and add it to a playbook node.
- Add a unit test for it in `tests/test_whygraph.py` and a handler in `tests/fake_store.py`.
- Record what you changed in the README disclosure paragraph.
