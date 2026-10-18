"""Thin wrapper around the FalkorDB Python client.

Every query goes through Ctx.q(), which also records a "receipt"
(Cypher text, parameters, row count, timing) so the UI can show exactly
what the graph was asked. FalkorDB multi-graph is used for tenancy:
one isolated graph per team (team_lumen, team_orbit).
"""
import time

from .config import cfg


class Store:
    def __init__(self):
        from falkordb import FalkorDB  # imported lazily so unit tests run without the package

        if cfg.falkor_url:
            self.db = FalkorDB.from_url(cfg.falkor_url)
        else:
            kwargs = {"host": cfg.falkor_host, "port": cfg.falkor_port}
            if cfg.falkor_username:
                kwargs["username"] = cfg.falkor_username
            if cfg.falkor_password:
                kwargs["password"] = cfg.falkor_password
            if cfg.falkor_ssl:
                kwargs["ssl"] = True
            self.db = FalkorDB(**kwargs)

    def graph(self, tenant):
        return self.db.select_graph(cfg.graph_prefix + tenant)

    def run(self, tenant, name, cypher, params=None, receipts=None):
        graph = self.graph(tenant)
        started = time.perf_counter()
        result = graph.query(cypher, params) if params else graph.query(cypher)
        ms = round((time.perf_counter() - started) * 1000, 1)
        rows = result.result_set or []
        if receipts is not None:
            receipts.append(
                {
                    "name": name,
                    "cypher": " ".join(cypher.split()),
                    "params": params or {},
                    "rows": len(rows),
                    "ms": ms,
                }
            )
        return rows

    def delete_graph(self, tenant):
        try:
            self.graph(tenant).delete()
        except Exception:
            pass  # the graph did not exist yet


class Ctx:
    """One request: a store, a tenant and the list of receipts collected so far."""

    def __init__(self, store, tenant):
        self.store = store
        self.tenant = tenant
        self.receipts = []

    def q(self, name, cypher, params=None, quiet=False):
        return self.store.run(self.tenant, name, cypher, params, None if quiet else self.receipts)

    def tick(self, name, engine, detail):
        """Record a non-Cypher step (e.g. a Python fallback) so the receipt stays honest."""
        self.receipts.append({"name": name, "cypher": f"[{engine}] {detail}", "params": {}, "rows": 0, "ms": 0})
