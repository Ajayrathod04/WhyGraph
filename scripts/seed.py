"""Reload the synthetic seed data into FalkorDB (wipes the team graphs).   python scripts/seed.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from whygraph import loader  # noqa: E402
from whygraph.db import Store  # noqa: E402

store = Store()
for tenant, seed in loader.list_seeds().items():
    info = loader.load_tenant(store, seed)
    print(f"loaded {tenant}: {info['nodes']} nodes, {info['edges']} edges")
