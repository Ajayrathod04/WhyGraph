# Why We Replaced Our Confluence Black Hole with a FalkorDB Graph

*By Team Shunya Code (Ajay Rathod) &bull; Built for WeMakeDevs &times; FalkorDB Graph Hacks 2026*

---

Every engineering team has a graveyard of decisions. 

Six months ago, someone moved a critical service from RabbitMQ to Kafka. Three months later, another team switched fraud detection providers. Today, an outage strikes, or an engineer proposes "cleaning up" an old queue, and the slack thread instantly spirals:
- *"Why did we move that queue in the first place?"*
- *"Who signed off on it?"*
- *"If we rollback, what breaks downstream?"*
- *"Is the benchmark document we based this on still valid?"*

Usually, the answer is lost in a 40-page Confluence page that hasn't been updated in two quarters, or in an archived Slack channel belonging to an engineer who left the company last year.

We built **WhyGraph / RECALL** to solve this exact problem: an auditable, graph-backed organizational brain that remembers **why** decisions were made, tests whether the supporting evidence is still fresh, and models the blast radius before changes ship.

---

## Why Relational Tables and Flat Vector Search Fail

When we first sat down to design the memory system for our AI agents, the obvious temptation was to drop architectural decision records (ADRs) into a vector database and perform similarity search (RAG).

Vector similarity search failed immediately on three fundamental questions:
1. **Multi-Hop Lineage:** If Decision A was based on Benchmark Study 1, but Benchmark Study 2 superseded Study 1, is Decision A still valid? A semantic embedding search matches the keywords in Study 1, completely unaware of the directional supersession edge connecting it to Study 2.
2. **Blast Radius Analysis:** *"If Service X fails, what downstream services break?"* In an enterprise architecture, dependencies are cyclic, variable-length directed graphs (`Service A -> Service B -> Service C -> Service D`). Relational SQL requires slow, complex recursive common table expressions (CTEs); vector search cannot traverse dependencies at all.
3. **Ownership and Accountability:** Connecting the system to the decision, the decision to the author, the author to their team, and the team to the services they maintain requires joining across six disparate entity types.

A graph database is the only natural data structure where entities (Decisions, Documents, Systems, People, Teams, Tasks) and their relationships (`DECIDED_BY`, `SUPPORTED_BY`, `DEPENDS_ON`, `SUPERSEDES`, `OWNS`) exist as first-class citizens.

---

## The Graph Data Model

We modeled our company memory in FalkorDB with 10 node labels and 15 relationship types:

- **Nodes:** `Person`, `Team`, `Project`, `System`, `Decision`, `Document`, `Question`, `Task`, `ChangeRequest`, `Playbook`.
- **Key Edges:**
  - `(:Decision)-[:SUPPORTED_BY]->(:Document)`
  - `(:Document)-[:SUPERSEDES]->(:Document)`
  - `(:System)-[:DEPENDS_ON]->(:System)`
  - `(:Person)-[:MEMBER_OF]->(:Team)-[:OWNS]->(:System)`
  - `(:Task)-[:ABOUT]->(:Decision)`

To ensure zero cross-tenant contamination between different departments or portfolio companies, we leveraged FalkorDB's multi-graph architecture: `team_lumen` (Lumen Payments) and `team_orbit` (Orbit Logistics) run in completely isolated graph spaces.

---

## Three Cypher Queries That Power the Brain

All reasoning in WhyGraph is driven by parameterized Cypher executed directly against FalkorDB. Here are three queries that do the heavy lifting:

### 1. Tracing Decision Lineage with Variable-Length Traversals
When a user asks why a decision was made, we traverse backwards to find the supporting documents, forward to find subsequent revisions, and across to discover the authors:

```cypher
MATCH (d:Decision {id: $id})
OPTIONAL MATCH (d)-[:DECIDED_BY]->(p:Person)-[:MEMBER_OF]->(t:Team)
OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(doc:Document)
OPTIONAL MATCH (d)-[:SUPERSEDES*1..6]->(older:Decision)
OPTIONAL MATCH (newer:Decision)-[:SUPERSEDES*1..6]->(d)
RETURN d, collect(distinct p), collect(distinct doc), 
       collect(distinct older), collect(distinct newer)
```

### 2. Multi-Hop Blast Radius & Native PageRank
To determine what breaks if an architectural change is made, we traverse variable-length dependency chains (`DEPENDS_ON*1..4`) and rank affected services using FalkorDB's native graph algorithms:

```cypher
MATCH path = (root:System {id: $id})<-[:DEPENDS_ON*1..4]-(dep:System)
RETURN dep.id, dep.name, dep.criticality, min(length(path)) AS hops
ORDER BY hops ASC, dep.criticality DESC
```
In parallel, we execute FalkorDB's native PageRank algorithm:
```cypher
CALL algo.pageRank('System', 'DEPENDS_ON')
YIELD node, score
RETURN node.id, node.name, score ORDER BY score DESC
```
This instantly highlights high-centrality choke points (like the Event Bus or Payments Ledger) that sit in the critical failure path.

### 3. Detecting Stale Decisions via Supersession Chains
When a new engineering study or vendor review is published, how do we know which decisions are now resting on invalid assumptions?

```cypher
MATCH (d:Decision)-[:SUPPORTED_BY]->(old:Document)
WHERE old.status = 'outdated' OR old.status = 'superseded'
OPTIONAL MATCH (new:Document)-[:SUPERSEDES]->(old)
RETURN d.id, d.title, d.status, old.id, old.title, new.id, new.title
```

---

## Agent Coordination Without Direct Communication

In WhyGraph, two autonomous agents keep the graph healthy:
- **The Archivist:** Ingests incoming ADRs and research documents, detects when old evidence is replaced, marks superseded documents, and flags affected decisions as stale.
- **The Analyst:** Interprets user questions, executes procedural playbooks loaded from `(:Playbook)` nodes in the graph, evaluates blast radius, and drafts change plans.

Crucially, **the agents never call each other**. They communicate asynchronously by writing and claiming `(:Task)` nodes in FalkorDB:
1. When the Archivist marks ADR-014 as superseded by ADR-031, it creates an open `(:Task {stage: 'assess', assignee: 'analyst'})-[:ABOUT]->(:Decision)`.
2. The Analyst queries open tasks, executes the impact analysis playbook, updates the task stage to `recheck`, and writes a draft `ChangeRequest`.
3. The Archivist verifies the resolution and closes the task.

FalkorDB serves as both the semantic memory and the distributed coordination bus.

---

## Introducing Impact Lab & RECALL Copilot

To make this practical for engineering leadership, we created **Impact Lab** (`/impact-lab.html`): a change simulation studio designed with a retro-futuristic Cobalt Editorial and Y2K aesthetic.

In Impact Lab, engineers can:
- Simulate breaking changes (like reverting the Billing Service back to a legacy queue) and inspect the interactive SVG dependency graph.
- Inspect the exact downstream blast radius, hop distance, and native PageRank scores.
- Review accountable stakeholders and deciders who must approve the change.
- Chat with **RECALL Copilot**: a friendly, 3D sculptural robot assistant that answers questions grounded in live FalkorDB queries, providing clickable citation pills and exact Cypher query receipts with sub-10ms execution times.
- Generate auditable rollback plans under a strict safety boundary: `DRAFT — HUMAN APPROVAL REQUIRED`.

---

## What We Learned

1. **Sub-10ms Latency Changes Agent Feasibility:** Running complex multi-hop Cypher queries in FalkorDB took between 4ms and 12ms. Because the database is fast, an agent can afford to execute 15–20 graph queries to answer a single question without human-perceptible lag.
2. **Deterministic Fallbacks Are Vital:** LLMs hallucinate dependencies when given raw unstructured text. By forcing our agents to extract grounded facts from the graph and return exact Cypher receipts, every answer is 100% explainable and verifiable.

---

## Try It Yourself

- **GitHub Repository:** [https://github.com/Ajayrathod04/WhyGraph](https://github.com/Ajayrathod04/WhyGraph)
- **Built With:** FalkorDB, Python, Docker Compose, Vanilla HTML/CSS/SVG.
- **Run Locally in 1 Command:**
  ```bash
  docker compose up -d
  pip install -r requirements.txt
  python -m whygraph
  ```
- **Visit:** `http://127.0.0.1:8000` (Home Brain) & `http://127.0.0.1:8000/impact-lab.html` (Impact Lab).
