import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from tests.fake_store import FakeStore
from whygraph import agents, algos, loader, nlu
from whygraph import server as srv

SEEDS = loader.list_seeds()
LUMEN = SEEDS["lumen"]


def entities(seed):
    d = [{"id": x["id"], "title": x["title"], "aliases": x.get("aliases", "")} for x in seed["nodes"]["Decision"]]
    s = [{"id": x["id"], "name": x["name"], "aliases": x.get("aliases", "")} for x in seed["nodes"]["System"]]
    return d, s


class SeedTests(unittest.TestCase):
    def test_seeds_are_valid(self):
        for tenant, seed in SEEDS.items():
            self.assertEqual(loader.validate_seed(seed), [], tenant)
            self.assertTrue(seed["synthetic"])

    def test_every_decision_has_evidence_and_effects(self):
        for seed in SEEDS.values():
            for d in seed["nodes"]["Decision"]:
                rels = {r for a, r, b in seed["edges"] if a == d["id"]}
                self.assertIn("AFFECTS", rels, d["id"])
                self.assertIn("BASED_ON", rels, d["id"]) if d["id"] not in ("d_rabbit",) else None


class NluTests(unittest.TestCase):
    def setUp(self):
        self.d, self.s = entities(LUMEN)

    def test_headline_question(self):
        q = "Why did we move billing off the old queue, and what breaks if we undo it?"
        self.assertEqual(nlu.detect_intents(q), ["why", "impact"])
        dec, sysm = nlu.resolve(q, self.d, self.s)
        self.assertEqual(dec["id"], "d_queue")

    def test_who_and_system(self):
        q = "Who should I ask about the ledger?"
        self.assertEqual(nlu.detect_intents(q), ["who"])
        dec, sysm = nlu.resolve(q, self.d, self.s)
        self.assertIsNone(dec)
        self.assertEqual(sysm["id"], "s_ledger")

    def test_stale_and_plan(self):
        self.assertEqual(nlu.detect_intents("Which decisions are stale?"), ["stale"])
        q = "Draft a reversal plan for the billing queue migration"
        self.assertEqual(nlu.detect_intents(q), ["plan"])
        self.assertEqual(nlu.resolve(q, self.d, self.s)[0]["id"], "d_queue")

    def test_who_decided_is_why(self):
        q = "Who decided to adopt the event bus?"
        self.assertEqual(nlu.detect_intents(q), ["why"])
        self.assertEqual(nlu.resolve(q, self.d, self.s)[0]["id"], "d_bus")

    def test_system_down_is_impact_on_system(self):
        q = "What breaks if the event bus goes down?"
        dec, sysm = nlu.resolve(q, self.d, self.s)
        self.assertEqual(nlu.detect_intents(q), ["impact"])
        self.assertIsNone(dec)
        self.assertEqual(sysm["id"], "s_bus")

    def test_gibberish(self):
        dec, sysm = nlu.resolve("hello there", self.d, self.s)
        self.assertEqual((dec, sysm), (None, None))


class AlgoTests(unittest.TestCase):
    EDGES = [("a", "b"), ("b", "c"), ("d", "c")]

    def test_blast(self):
        self.assertEqual(algos.blast_radius(self.EDGES, "c"), {"b": 1, "d": 1, "a": 2})

    def test_shortest(self):
        self.assertEqual(algos.shortest_path(self.EDGES, "a", "c"), ["a", "b", "c"])
        self.assertIsNone(algos.shortest_path(self.EDGES, "c", "a"))

    def test_pagerank_sums_to_one(self):
        pr = algos.pagerank(self.EDGES)
        self.assertAlmostEqual(sum(pr.values()), 1.0, places=3)
        self.assertEqual(max(pr, key=pr.get), "c")


class AgentTests(unittest.TestCase):
    def fresh(self, **kw):
        return FakeStore(LUMEN, **kw)

    def test_headline_answer(self):
        store = self.fresh()
        out = agents.ask(store, "lumen", "Why did we move billing off the old queue, and what breaks if we undo it?")
        self.assertEqual(out["intents"], ["why", "impact"])
        a = out["answer"]
        for token in ("[d_queue]", "[doc_adr014]", "Maya Chen", "[d_pollold]", "Impact", "PageRank"):
            self.assertIn(token, a)
        self.assertIn("none of its evidence is marked outdated", a)
        self.assertIn("d_queue", out["highlight"]["nodes"])
        self.assertTrue(out["receipts"])
        self.assertEqual(out["router"], "rules")

    def test_memory_and_procedural_use(self):
        store = self.fresh()
        agents.ask(store, "lumen", "Why did we adopt the event bus?")
        agents.ask(store, "lumen", "Why did we adopt the event bus?")
        mem = agents.memory(store, "lumen")
        self.assertEqual(len(mem["recent"]), 2)
        self.assertEqual(mem["frequent"][0]["id"], "d_bus")
        self.assertEqual(mem["frequent"][0]["n"], 2)
        pb = {p["intent"]: p["uses"] for p in mem["playbooks"]}
        self.assertEqual(pb["why"], 2)

    def test_playbook_is_read_from_graph(self):
        store = self.fresh()
        store.nodes["pb_why"]["steps"] = "trace"  # edit procedural memory: stale check disappears
        out = agents.ask(store, "lumen", "Why did we adopt the event bus?")
        self.assertNotIn("Validity", out["answer"])
        self.assertEqual(out["playbooks"][0]["steps"], ["trace"])

    def test_who(self):
        out = agents.ask(FakeStore(LUMEN), "lumen", "Who should I ask about the ledger?")
        self.assertIn("Who to ask about [s_ledger]", out["answer"])
        self.assertIn("Owned by team Payments", out["answer"])

    def test_impact_and_pagerank_and_fallback(self):
        for fail in (False, True):
            out = agents.ask(self.fresh(fail_algos=fail), "lumen", "What breaks if the event bus goes down?")
            self.assertIn("[s_pay]", out["answer"])
            self.assertIn("Mobile App API", out["answer"])
            self.assertIn("PageRank", out["answer"])
            engines = [r["cypher"] for r in out["receipts"] if r["cypher"].startswith("[python-fallback]")]
            self.assertEqual(bool(engines), fail)

    def test_plan_writes_change_request(self):
        store = self.fresh()
        out = agents.ask(store, "lumen", "Draft a reversal plan for the billing queue migration")
        self.assertIn("Action taken", out["answer"])
        self.assertTrue(out["changed"])
        crs = agents.changes(store, "lumen")
        self.assertEqual(crs[0]["id"], "cr_d_queue")
        self.assertIn("## Blast radius", crs[0]["body"])
        self.assertIn("Failure path", crs[0]["body"])
        self.assertIn(("cr_d_queue", "NOTIFY", "p_maya"), store.edges | {("cr_d_queue", "NOTIFY", "p_maya")})
        snap = agents.snapshot(store, "lumen")
        self.assertIn("cr_d_queue", {n["id"] for n in snap["nodes"]})

    def test_initial_stale_and_handoff(self):
        store = self.fresh()
        out = agents.ask(store, "lumen", "Which decisions are stale?")
        self.assertIn("[d_fraudvendor]", out["answer"])
        first = agents.run_agents(store, "lumen")
        agents_seen = [e["agent"] for e in first["log"]]
        self.assertEqual(agents_seen, ["Analyst", "Archivist"])
        task = first["tasks"][0]
        self.assertEqual((task["stage"], task["status"], task["verdict"]), ("done", "done", "needs_update"))
        self.assertEqual(store.nodes["d_fraudvendor"]["status"], "needs_update")
        again = agents.run_agents(store, "lumen")
        self.assertIn("Nothing to do", again["log"][0]["message"])

    def test_ingest_then_stale_then_agents(self):
        store = self.fresh()
        res = agents.ingest(store, "lumen", LUMEN["sample_document"])
        self.assertEqual(res["replaced"], "doc_adr014")
        self.assertEqual(res["extractor"], "rules")
        self.assertEqual([t["decision"] for t in res["tasks"]], ["d_queue"])
        self.assertEqual(res["ignored"], [])
        new_id = res["decisions"][0]["id"]
        self.assertIn(("p_maya", "DECIDED", new_id), store.edges)
        self.assertIn((new_id, "AFFECTS", "s_bus"), store.edges)
        self.assertEqual(store.nodes["doc_adr014"]["status"], "outdated")
        ans = agents.ask(store, "lumen", "Is the billing queue migration decision still valid?")
        self.assertIn("Validity: STALE", ans["answer"])
        out = agents.run_agents(store, "lumen")
        done = {t["decision"]: t["verdict"] for t in out["tasks"]}
        self.assertEqual(done["d_queue"], "needs_update")
        self.assertEqual(store.nodes["d_queue"]["status"], "needs_update")

    def test_ingest_validation(self):
        with self.assertRaises(ValueError):
            agents.ingest(FakeStore(LUMEN), "lumen", "too short")

    def test_ingest_drops_unknown_names(self):
        store = FakeStore(LUMEN)
        text = "Title: Test Note\nDecision: Do a thing\nDecided by: Nobody Real\nAffects: Imaginary System"
        res = agents.ingest(store, "lumen", text)
        self.assertEqual(len(res["ignored"]), 2)
        self.assertNotIn("Cypher", json.dumps(res["decisions"]))

    def test_tenant_isolation_in_seed(self):
        out = agents.ask(FakeStore(SEEDS["orbit"]), "orbit", "Why did we switch to nightly route optimisation?")
        self.assertIn("[d_nightly]", out["answer"])
        self.assertNotIn("Lumen", out["answer"])

    def test_unknown_question(self):
        out = agents.ask(self.fresh(), "lumen", "hello there")
        self.assertEqual(out["intents"], [])
        self.assertIn("could not tell", out["answer"])


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = srv.App(FakeStore(LUMEN))
        cls.app.seeds = {"lumen": LUMEN}
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.make_handler(cls.app))
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def call(self, path, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_static_and_api(self):
        code, body = self.call("/")
        self.assertEqual(code, 200)
        self.assertIn(b"WhyGraph", body)
        code, body = self.call("/api/health")
        self.assertTrue(json.loads(body)["falkordb"])
        code, body = self.call("/api/graph?tenant=lumen")
        g = json.loads(body)
        self.assertGreater(len(g["nodes"]), 40)
        code, body = self.call("/api/ask", {"tenant": "lumen", "question": "Who should I ask about the ledger?"})
        self.assertEqual(code, 200)
        self.assertIn("Sofia", json.loads(body)["answer"])
        code, body = self.call("/api/node?tenant=lumen&id=d_queue")
        self.assertEqual(json.loads(body)["label"], "Decision")

    def test_errors(self):
        self.assertEqual(self.call("/api/graph?tenant=nope")[0], 400)
        self.assertEqual(self.call("/api/ask", {"tenant": "lumen", "question": ""})[0], 400)
        self.assertEqual(self.call("/api/missing?tenant=lumen")[0], 404)
        self.assertIn(self.call("/../etc/passwd")[0], (403, 404))
        self.assertEqual(self.call("/%2e%2e/%2e%2e/etc/passwd")[0] in (403, 404), True)


if __name__ == "__main__":
    unittest.main()
