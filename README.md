# WhyGraph: the company brain that remembers why

> Built for **Graph Hacks: Context for AI Agents** (WeMakeDevs x FalkorDB). Tracks entered: **01 Agents That Act on Connected Data**, **02 Agent Memory and Coordination**, **03 Company Brain**.

Ask *"Why did we move billing off the old queue, and what breaks if we undo it?"* and WhyGraph answers by **walking a FalkorDB graph** of people, teams, systems, documents and decisions. Every claim carries a source tag, the path the agent walked lights up in the graph, and the exact Cypher behind the answer is one click away (the "receipt").

Two cooperating agents keep the brain honest:

- **Analyst** answers questions with *playbooks stored in the graph*, remembers every question, and takes action (writes a draft change request and links the people to notify).
- **Archivist** ingests new documents, marks outdated evidence, and re-checks decisions that now rest on it.

They never call each other. They hand work over through `(:Task)` nodes in the shared graph: `open -> Analyst assesses -> Archivist re-checks -> done`.

## Why the graph is essential (rule 3)

Take FalkorDB away and the product does not start. There is no second data store and no in-memory fallback in the shipped code.

| Capability | How the graph does the work |
|---|---|
| Why was it decided? | `DECIDED`, `BASED_ON`, `SUPERSEDES*1..6` traversals |
| What breaks if it changes? | `DEPENDS_ON*1..4` variable-length paths, `algo.pageRank`, `shortestPath` |
| Who should I ask? | `KNOWS`, `WORKED_ON -> USES`, `DECIDED -> AFFECTS`, `OWNS` joined in one query family |
| Is knowledge current? | `BASED_ON -> Document {status:'outdated'} -[:REPLACED_BY]-> Document` |
| Memory per team | One isolated FalkorDB graph per tenant (`team_lumen`, `team_orbit`) |
| Agent hand-off | `(:Task)-[:ABOUT]->(:Decision)` with `stage` and `assignee` |
| Procedural memory | `(:Playbook {steps})` nodes the Analyst reads at runtime |
| Action | `(:ChangeRequest)-[:PROPOSES_REVERSAL_OF]->(:Decision)` and `-[:NOTIFY]->(:Person)` |

All Cypher lives in [`whygraph/queries.py`](whygraph/queries.py). Values are always passed as parameters; user or document text is never concatenated into a query.

## How it covers the three tracks

| Track | Brief (from the event page) | In WhyGraph |
|---|---|---|
| 01 Act on connected data | multi-hop reasoning, algorithms as tools, explainable results | variable-length paths, PageRank ranking, shortest dependency chain; the `plan` action writes a `ChangeRequest`; every answer ships its Cypher receipt |
| 02 Memory and coordination | episodic/semantic/procedural memory, shared state and hand-offs, separate memory per tenant | `Question` nodes (episodic) bias later entity resolution; the knowledge graph is semantic memory; `Playbook` nodes drive tool order (procedural); `Task` nodes are the hand-off channel; one graph per team |
| 03 Company Brain | decisions traced to source, who owns/knows what, knowledge kept current, answers with sources | `Decision -> Document` evidence, `OWNS`/`KNOWS` edges, an ingest flow that marks superseded documents and surfaces stale decisions, `[source]` tags on every claim |

## Quick start

Requirements: **Docker Desktop**, **Python 3.10+**. The only Python dependency is the `falkordb` client (the web server is the Python standard library).

**Windows:** double-click `run.bat` (or run it in a terminal).
**macOS / Linux:** `./run.sh`

Manual steps (same thing):

```bash
docker compose up -d                 # FalkorDB on :6379, FalkorDB Browser on http://localhost:3000
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m whygraph                   # seeds the synthetic data on first start, then serves http://127.0.0.1:8000
```

Open **http://127.0.0.1:8000**. No API key is needed: without one the app runs in *offline mode* (deterministic answers composed from graph facts). Add `LLM_API_KEY` in `.env` (see `.env.example`) to have an LLM route questions and phrase answers; it still may only use graph facts.

**FalkorDB Cloud instead of Docker:** put host, port, username and password in `.env` (`FALKORDB_*`).

### Verify everything against YOUR FalkorDB (recommended, 20 seconds)

```bash
python scripts/selfcheck.py
```

It runs every Cypher query and both graph algorithms on throw-away graphs, then replays the whole demo. `WARN` on an algorithm means your FalkorDB version rejected that call; the app then uses a documented Python fallback over edges it read from FalkorDB, and the receipt says so.

### Open in Google Antigravity (or any IDE)

1. Open this folder as the workspace. 2. Run `docker compose up -d` in its terminal. 3. `pip install -r requirements.txt` then `python scripts/selfcheck.py`. 4. `python -m whygraph`. [`AGENTS.md`](AGENTS.md) tells a coding agent the project rules.

## 3-minute demo path

1. Pick **Lumen Payments**. Click the first example question. Watch the path light up and read the receipt.
2. Notice the red **stale** decision already in the Agents tab (the fraud vendor review was replaced).
3. **Ingest** tab, **Load sample**, **Ingest as Archivist**: a new document replaces ADR-014, so the billing decision turns stale and a task is opened.
4. **Agents** tab, **Run both agents**: Analyst assesses the blast radius, Archivist re-checks and closes the tasks.
5. Ask *"Is the fraud vendor decision still valid?"* then *"Draft a reversal plan for the billing queue migration"* and open the **Changes** tab.
6. Switch to **Orbit Logistics** to show isolated memory. Open the **Memory** tab to show episodic and procedural memory.
7. Open FalkorDB Browser (http://localhost:3000) and show the same graph.

## Architecture

```
web/            index.html, app.css, app.js     SVG graph (own force layout), answers, agents, ingest, memory
whygraph/
  server.py     stdlib HTTP server + JSON API   /api/ask /api/graph /api/agents/run /api/ingest ...
  agents.py     Analyst + Archivist + tools     playbook engine, hand-off loop, ingest, answer composition
  queries.py    ALL Cypher                      read this to see what the product asks the graph
  loader.py     seed loader                     whitelisted labels/relationships/properties, parameterised values
  nlu.py        intent + entity resolution      deterministic; no LLM required
  llm.py        optional OpenAI-compatible LLM  routing, phrasing, extraction, verdict (all validated)
  algos.py      Python fallbacks               used only if a FalkorDB call is rejected; still reads edges from FalkorDB
seed/           two SYNTHETIC companies         lumen_payments.json, orbit_logistics.json
scripts/        selfcheck.py, seed.py, make_seed.py
tests/          unit tests (stand-in store, see below)
```

### Graph data model

Nodes: `Person, Team, Project, System, Decision, Document, Question, Task, ChangeRequest, Playbook`.
Relationships: `MEMBER_OF, OWNS, WORKED_ON, USES, KNOWS, DEPENDS_ON, DECIDED, BASED_ON, AFFECTS, SUPERSEDES, REPLACED_BY, VIEWED, ABOUT, PROPOSES_REVERSAL_OF, NOTIFY`.
Full diagram in the docstring at the top of `whygraph/queries.py`.

### Graph tools the Analyst can call

| Tool | Cypher / algorithm | Used by playbook |
|---|---|---|
| `trace` | `DECIDED`, `BASED_ON`, `SUPERSEDES*1..6` (both directions), `AFFECTS` | why |
| `stale_check`, `stale_scan` | `BASED_ON -> Document {status:'outdated'}` + `OPTIONAL MATCH REPLACED_BY` | why, stale |
| `who_knows` | `KNOWS`, `WORKED_ON->USES`, `DECIDED->AFFECTS`, `OWNS` | who |
| `impact` | `DEPENDS_ON*1..4` with `min(length(path))` | impact, plan |
| `pagerank` | `CALL algo.pageRank('System','DEPENDS_ON')` | impact, plan |
| `shortest_path` | `shortestPath((a)-[:DEPENDS_ON*]->(b))` | plan |
| `plan` (action) | writes `ChangeRequest` + `NOTIFY` edges | plan |

## Rules compliance (Graph Hacks rules page)

| Rule | How this project complies |
|---|---|
| 2 FalkorDB primary and central | The only database; every feature runs on it |
| 3 Graph does real work | See the table above; app refuses to start without FalkorDB |
| 4 Run FalkorDB any way | Docker Compose (default) or FalkorDB Cloud via `.env` |
| 5 Name every track | Tracks 01, 02, 03 are named in the submission form |
| 6 Allowed data only | **Synthetic** fictional companies and people only. No private, personal, login-protected or paywalled data |
| 8-9 New work during the event | Written during the hackathon window; only open-source libraries used (`falkordb` client) |
| 10 Submission contents | Public repo, this README (setup + data model), queries in `whygraph/queries.py`, demo video, local setup instructions, tracks |
| 11 Disclose AI assistance | See below |
| 12 Understand the code | See [`EXPLAIN.md`](EXPLAIN.md) |

## AI assistance disclosure

The initial code, synthetic seed data, UI and documentation were produced with the help of **Claude (Anthropic)** working from the author's specification. System environment recovery, cloud deployment configuration (FalkorDB Cloud, Render), error-handling hardening, and live end-to-end FalkorDB verification were performed with **Antigravity (Google DeepMind)**. The author reviewed, tested, verified all queries against live FalkorDB, and is responsible for the project.

## Data statement

All data in `seed/` is synthetic: fictional companies (Lumen Payments, Orbit Logistics), fictional people, example.com-style placeholder URLs. Documents you paste into the Ingest tab are processed locally (and sent to your configured LLM provider only if you set `LLM_API_KEY`). Do not paste confidential material.

## Security notes

- Cypher parameters everywhere; labels, relationship types and property names in the loader are whitelisted.
- LLM output (routing, extraction, verdicts) is parsed as JSON and **validated against ids that exist in the graph**; it is never executed or concatenated into Cypher.
- Ingested documents are treated as untrusted data; text is length-limited and sanitised.
- The server binds to `127.0.0.1` by default, limits request size, and serves static files from `web/` only.

## Tests

```bash
python -m unittest tests.test_whygraph
```

The unit tests use `tests/fake_store.py`, an **in-memory stand-in used only by the tests** so the Python logic (routing, ranking, hand-off, ingest, API) can run without a database. It is not part of the product. The real Cypher is verified by `scripts/selfcheck.py` against a live FalkorDB.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Banner "FalkorDB is not reachable" | `docker compose up -d`, wait 5 seconds, reload |
| `ModuleNotFoundError: falkordb` | activate the venv, `pip install -r requirements.txt` |
| Port 8000 busy | set `PORT=8001` in `.env` |
| Port 6379 busy (another Redis) | change the left side of the port mapping in `docker-compose.yml` and set `FALKORDB_PORT` |
| Selfcheck FAIL on a query | copy the line here (it names the query) and check docs.falkordb.com/cypher for your version |
| Fonts look plain | Google Fonts need internet; the layout falls back to system fonts |

## Limitations (honest)

- Data is synthetic and small (about 50 nodes per team) by design; it demonstrates the model, not scale.
- Offline entity resolution is keyword/alias based; the optional LLM routing handles looser phrasing.
- The Archivist's offline verdict is conservative: if evidence was replaced it asks a human to re-validate rather than guessing.
- Graph-algorithm syntax can differ across FalkorDB versions (see `selfcheck.py` and the fallback note above).

## Credits

- Graph database: [FalkorDB](https://www.falkordb.com) (client `falkordb`, Python).
- Fonts via Google Fonts: Unbounded, DM Sans, JetBrains Mono (SIL Open Font License).
- UI direction (palette, chunky display type, hard-edged cards) was inspired by a mood board of colourful 3D lettering, an arcade website and poster art; colours were estimated by eye and no logos, artwork or layouts were copied.
- Licence: MIT (see `LICENSE`).
