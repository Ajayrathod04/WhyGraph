# Notes for coding agents (Antigravity, Claude Code, Cursor ...)

Project: WhyGraph, a FalkorDB-backed "company brain" for the Graph Hacks hackathon.

Rules you must keep:
1. FalkorDB stays the only data store. Do NOT add a non-FalkorDB fallback that lets the app run without it (hackathon rule 3).
2. All Cypher lives in `whygraph/queries.py` and uses parameters. Never build Cypher from user, document or LLM text. Labels / relationship types / property names are whitelisted in `whygraph/loader.py`.
3. Keep the dependency list at `falkordb` only. The server is stdlib on purpose.
4. Data must stay synthetic, public or the author's own. No personal or private data.
5. LLM output is untrusted: parse as JSON and validate ids against the graph before use.
6. Any AI-assisted change must be disclosed in the README "AI assistance disclosure" section.

Commands:
- `docker compose up -d` then `python -m whygraph`
- `python scripts/selfcheck.py` (needs FalkorDB; verifies every query)
- `python -m unittest tests.test_whygraph` (no database needed; uses tests/fake_store.py, test-only)
- `python scripts/make_seed.py` regenerates `seed/*.json`
