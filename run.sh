#!/usr/bin/env bash
# One-command start for macOS / Linux. Requires Docker and Python 3.10+.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
docker compose up -d
echo "Waiting for FalkorDB..."
sleep 4
python -m whygraph
