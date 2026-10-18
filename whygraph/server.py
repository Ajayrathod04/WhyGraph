"""HTTP server (Python standard library only): JSON API + the static web UI.

Run:  python -m whygraph
No web framework is needed, so the only third-party dependency of the whole project is the `falkordb` client.
"""
import json
import mimetypes
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import agents, llm, loader
from .config import cfg
from .db import Ctx
from . import queries as Q

MAX_BODY = 64 * 1024


class App:
    def __init__(self, store):
        self.store = store
        self.seeds = loader.list_seeds()

    def tenant(self, name):
        if name not in self.seeds:
            raise ValueError(f"Unknown tenant '{name}'. Known: {', '.join(self.seeds)}")
        return name

    def node_count(self, tenant):
        try:
            rows = Ctx(self.store, tenant).q("count", Q.Q_COUNT, quiet=True)
            return int(rows[0][0]) if rows else 0
        except Exception:
            return 0

    def ensure_loaded(self):
        """Load each tenant's seed on first start (an empty graph means 'not loaded yet')."""
        for tenant, seed in self.seeds.items():
            if self.node_count(tenant) == 0:
                info = loader.load_tenant(self.store, seed)
                print(f"[seed] loaded {tenant}: {info['nodes']} nodes, {info['edges']} edges", flush=True)

    def health(self):
        try:
            tenants = []
            for tenant, seed in self.seeds.items():
                tenants.append(
                    {
                        "id": tenant, "name": seed["name"], "blurb": seed.get("blurb", ""),
                        "examples": seed.get("examples", []), "sample_document": seed.get("sample_document", ""),
                        "nodes": self.node_count(tenant), "graph": cfg.graph_prefix + tenant,
                    }
                )
            return {"falkordb": True, "tenants": tenants, "llm": {"mode": llm.mode(), "model": cfg.llm_model if llm.enabled() else ""}}
        except Exception as exc:  # database not reachable
            return {"falkordb": False, "error": str(exc), "tenants": [], "llm": {"mode": llm.mode(), "model": ""}}

    # ---- routes: each returns a JSON-serialisable object
    def get(self, path, query):
        t = lambda: self.tenant(query.get("tenant", [""])[0])
        if path == "/api/health":
            return self.health()
        if path == "/api/graph":
            return agents.snapshot(self.store, t())
        if path == "/api/tasks":
            tenant = t()
            return {"tasks": agents.list_tasks(Ctx(self.store, tenant)), "stale": agents.stale_list(self.store, tenant)}
        if path == "/api/memory":
            return agents.memory(self.store, t())
        if path == "/api/changes":
            return {"changes": agents.changes(self.store, t())}
        if path == "/api/node":
            return agents.node_detail(self.store, t(), query.get("id", [""])[0])
        raise KeyError(path)

    def post(self, path, body):
        tenant = self.tenant(body.get("tenant", ""))
        if path == "/api/ask":
            return agents.ask(self.store, tenant, body.get("question", ""))
        if path == "/api/agents/run":
            return agents.run_agents(self.store, tenant)
        if path == "/api/ingest":
            return agents.ingest(self.store, tenant, body.get("text", ""))
        if path == "/api/reset":
            info = loader.load_tenant(self.store, self.seeds[tenant])
            return {"ok": True, **info}
        raise KeyError(path)


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "WhyGraph/1.0"

        def log_message(self, fmt, *args):  # quieter console
            sys.stderr.write("[http] " + (fmt % args) + "\n")

        def _json(self, status, payload):
            data = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _guard(self, fn):
            try:
                self._json(200, fn())
            except KeyError:
                self._json(404, {"error": "Not found"})
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except Exception as exc:
                traceback.print_exc()
                self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

        def do_GET(self):
            url = urlparse(self.path)
            if url.path.startswith("/api/"):
                return self._guard(lambda: app.get(url.path, parse_qs(url.query)))
            return self._static(url.path)

        def do_POST(self):
            url = urlparse(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._json(413, {"error": "Request too large"})
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except ValueError:
                return self._json(400, {"error": "Body must be JSON"})
            if not isinstance(body, dict):
                return self._json(400, {"error": "Body must be a JSON object"})
            return self._guard(lambda: app.post(url.path, body))

        def _static(self, path):
            if path in ("", "/"):
                rel = "index.html"
            elif path in ("/impact-lab", "/impact-lab/"):
                rel = "impact-lab.html"
            else:
                rel = path.lstrip("/")
            target = (cfg.web_dir / rel).resolve()
            if cfg.web_dir.resolve() not in target.parents and target != cfg.web_dir.resolve():
                return self._json(403, {"error": "Forbidden"})
            if not target.is_file():
                return self._json(404, {"error": "Not found"})
            data = target.read_bytes()
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("javascript") else ""))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    return Handler


def serve(store=None):
    from .db import Store

    try:
        store = store or Store()
    except ImportError:
        print("[error] the 'falkordb' package is not installed. Activate your virtualenv and run:  pip install -r requirements.txt")
        raise SystemExit(1)
    except Exception as exc:
        print(f"[warn] could not reach FalkorDB at {cfg.falkor_host}:{cfg.falkor_port}: {exc}")
        print("       Start it with:  docker compose up -d   (then restart this server)")
        raise SystemExit(1)
    app = App(store)
    try:
        app.ensure_loaded()
    except Exception as exc:
        print(f"[warn] could not reach FalkorDB at {cfg.falkor_host}:{cfg.falkor_port}: {exc}")
        print("       Start it with:  docker compose up -d   (then restart this server)")
        raise SystemExit(1)
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(app))
    print(f"WhyGraph running at http://{cfg.host}:{cfg.port}   (LLM mode: {llm.mode()})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
