"""Configuration: environment variables, optionally read from a .env file."""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_env_file():
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Config:
    # FalkorDB: local Docker by default. FalkorDB Cloud also works via host/port/username/password or URL.
    falkor_url = os.environ.get("FALKORDB_URL", "")
    falkor_host = os.environ.get("FALKORDB_HOST", "localhost")
    falkor_port = _int("FALKORDB_PORT", 6379)
    falkor_username = os.environ.get("FALKORDB_USERNAME", "")
    falkor_password = os.environ.get("FALKORDB_PASSWORD", "")
    falkor_ssl = os.environ.get("FALKORDB_SSL", "").lower() in ("true", "1", "yes")
    graph_prefix = os.environ.get("GRAPH_PREFIX", "team_")  # one graph per tenant: team_lumen, team_orbit

    # Optional LLM: any OpenAI-compatible /chat/completions endpoint. Empty key = offline mode.
    llm_base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    llm_api_key = os.environ.get("LLM_API_KEY", "")
    llm_model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("RENDER") else "127.0.0.1")
    port = _int("PORT", 8000)

    seed_dir = ROOT / "seed"
    web_dir = ROOT / "web"


cfg = Config()
