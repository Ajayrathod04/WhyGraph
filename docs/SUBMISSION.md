# Submission pack for the Graph Hacks form

Submission page fields (from the event page): Project title, Description, Track(s), Repository, Demo video (YouTube, public or unlisted), Live demo (optional), How did you use FalkorDB, Blog link (optional), and two required feedback answers. You can edit the submission until the deadline (18 Oct 2026, 11:59 PM IST). You cannot change your team after submitting.

## Form answers (edit the brackets; keep it truthful)

**Project title:** WhyGraph

**Description (what problem, who for):**
Companies lose the reasons behind decisions. New engineering leads and product managers can't tell why something was decided, who knows about it, what breaks if it changes, or whether the evidence is still valid. WhyGraph is a company brain on FalkorDB: two cooperating agents (Analyst and Archivist) answer those questions by walking a graph of people, teams, systems, documents and decisions, and show the exact path and Cypher behind every answer. It also keeps knowledge current: when a new document replaces old evidence, dependent decisions are flagged stale and handed from one agent to the other through Task nodes. It runs on synthetic data for two fictional companies, each in its own FalkorDB graph.

**Tracks:** select all three only if you demo all three (Company Brain, Agents That Act on Connected Data, Agent Memory and Coordination). If you cut scope, deselect the track you did not finish.

**Repository:** https://github.com/Ajayrathod04/WhyGraph (public)

**Demo video:** [YouTube link, public or unlisted]

**Live demo or deployment:** Local setup instructions verified on Windows/macOS/Linux via Docker Compose (see README).

**How did you use FalkorDB (technical problems solved):**
- One isolated graph per team using FalkorDB multi-graph (`team_lumen`, `team_orbit`), so memory never leaks between tenants.
- Why-tracing with variable-length paths (`SUPERSEDES*1..6`, `BASED_ON`) to follow decisions back to documents and through replaced decisions.
- Blast radius with `DEPENDS_ON*1..4` and `min(length(path))`, ranked with native `algo.pageRank`, plus `shortestPath` for the dependency chain, all exposed as agent tools.
- Stale-knowledge detection with `OPTIONAL MATCH` over `Document {status:'outdated'} -[:REPLACED_BY]->`.
- Agent coordination by writing and reading `Task` nodes (stage and assignee) instead of direct calls; `MERGE ... ON CREATE SET` makes hand-offs idempotent.
- Memory in the graph: `Question` nodes (episodic) that bias entity resolution, and `Playbook` nodes (procedural) that the agent reads to decide which tools to run.
- Action drafts written back to the graph: `ChangeRequest` nodes linked to the decision and to people to notify.
- **Impact Lab**: Dedicated change simulation studio (`/impact-lab.html`) simulating queue reversals, evidence invalidation, and live ADR ingestion.
- Without FalkorDB the product does not start: there is no other data store.
- **Verified Metrics**: `scripts/selfcheck.py` verifies 36/36 checks (0 failures, 0 warnings); headline questions complete in 20 graph calls within ~96ms; unit test suite passes 25/25 tests.

**Blog link:** [after you publish]

**Feedback: what did you like about FalkorDB? / what improvements would you like?** Write these yourself from what you actually experienced while building (setup, Cypher support, the Browser, docs, errors you hit). Keep a note of anything confusing as you go; honest specifics read better than praise.

## Demo video: 3 minutes, record at 1080p, upload to YouTube as Unlisted

| Time | Show | Say |
|---|---|---|
| 0:00-0:20 | App open on Lumen; click example question 1 | "New leads can't tell why decisions were made. Watch the graph answer." |
| 0:20-1:00 | Path lights up; click a source chip; expand Receipt | "Every claim has a source. This is the exact Cypher FalkorDB ran." |
| 1:00-1:35 | Ingest tab, load sample, ingest | "A new document replaces an old study. The Archivist marks it outdated." |
| 1:35-2:00 | Agents tab, Run both agents | "Analyst assesses blast radius with PageRank, hands over via a Task node, Archivist re-checks." |
| 2:00-2:25 | Ask "Draft a reversal plan..." then Changes tab | "The agent acts: a change request is written into the graph and linked to who to notify." |
| 2:25-2:45 | Switch to Orbit; Memory tab | "One graph per team. Questions and playbooks are memory in the graph." |
| 2:45-3:00 | FalkorDB Browser at localhost:3000 | "Same graph in FalkorDB Browser. Without it, the product doesn't run." |

Recording tips: browser zoom 110 percent, hide bookmarks, practice once, keep the cursor slow. Do a first pass without audio if you are short on time and add captions.

YouTube: upload, set visibility to **Unlisted** (or Public), copy the link, open it in a private window to confirm it plays.

## Blog post outline (optional prize; about 700 to 1000 words, written in your own words)

1. The problem: decisions without reasons. A short real-feeling story.
2. Why a table fails (joins across six kinds of things) and why a graph fits.
3. The model in one picture (screenshot of the graph).
4. Three queries that mattered: trace, blast radius, stale check (show the Cypher).
5. Two agents and a hand-off without calling each other (Task nodes).
6. What surprised you as a first-time graph builder (be specific and honest).
7. What you would build next. Link to repo and demo video.

## Final checklist (before you click Submit)

- [ ] Repo is **public**; README opens correctly; `.env` is not in the repo
- [ ] README AI-disclosure paragraph edited so it is exactly true
- [ ] `python scripts/selfcheck.py` result noted (and any WARN understood)
- [ ] Fresh clone test: `git clone`, `run.bat` or `./run.sh`, app opens
- [ ] Video plays in a private window; link pasted
- [ ] Tracks selected match what the demo shows
- [ ] Both feedback questions answered in your own words
- [ ] Re-read the live Rules page one last time (rules may be updated in the community channels)
- [ ] Screenshot of the submission confirmation
