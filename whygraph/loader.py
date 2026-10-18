"""Loads a seed JSON file into the tenant's FalkorDB graph.

Seed data is SYNTHETIC (fictional companies and people) so no private or personal data enters the graph.
Only whitelisted labels, relationship types and property names are ever put into Cypher text;
all values travel as query parameters.
"""
import json
import re

from .config import cfg

LABELS = {"Person", "Team", "Project", "System", "Decision", "Document", "Playbook"}
RELS = {
    "MEMBER_OF", "OWNS", "WORKED_ON", "USES", "KNOWS", "DEPENDS_ON", "DECIDED",
    "BASED_ON", "AFFECTS", "SUPERSEDES", "REPLACED_BY",
}
_PROP = re.compile(r"^[a-z_][a-z0-9_]*$")


def list_seeds():
    """Returns {tenant: seed_dict} for every seed/*.json file."""
    seeds = {}
    for path in sorted(cfg.seed_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        seeds[data["tenant"]] = data
    return seeds


def validate_seed(seed):
    """Referential-integrity check. Returns a list of problems (empty = fine)."""
    problems = []
    ids = {}
    for label, nodes in seed["nodes"].items():
        if label not in LABELS:
            problems.append(f"unknown label {label}")
        for node in nodes:
            if "id" not in node:
                problems.append(f"{label} without id")
                continue
            if node["id"] in ids:
                problems.append(f"duplicate id {node['id']}")
            ids[node["id"]] = label
            for key in node:
                if not _PROP.match(key):
                    problems.append(f"bad property name {key} on {node['id']}")
    for a, rel, b in seed["edges"]:
        if rel not in RELS:
            problems.append(f"unknown relationship {rel}")
        for end in (a, b):
            if end not in ids:
                problems.append(f"edge {a}-{rel}->{b}: missing node {end}")
    return problems


def load_tenant(store, seed):
    tenant = seed["tenant"]
    problems = validate_seed(seed)
    if problems:
        raise ValueError("invalid seed: " + "; ".join(problems[:5]))
    store.delete_graph(tenant)
    graph = store.graph(tenant)
    label_of = {}
    for label, nodes in seed["nodes"].items():
        for node in nodes:
            label_of[node["id"]] = label
            props = {k: v for k, v in node.items() if k != "id" and v is not None}
            sets = "".join(f", n.{k} = ${k}" for k in props)
            cypher = f"MERGE (n:{label} {{id: $id}}) SET n.seeded = true{sets}"
            graph.query(cypher, {"id": node["id"], **props})
    for a, rel, b in seed["edges"]:
        cypher = (
            f"MATCH (a:{label_of[a]} {{id: $a}}), (b:{label_of[b]} {{id: $b}}) "
            f"MERGE (a)-[:{rel}]->(b)"
        )
        graph.query(cypher, {"a": a, "b": b})
    for label in ("Person", "Team", "Project", "System", "Decision", "Document", "Task", "Question", "Playbook"):
        try:
            graph.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
        except Exception:
            pass  # index already exists or is unsupported: queries still work, only slower
    return {"nodes": len(label_of), "edges": len(seed["edges"])}
