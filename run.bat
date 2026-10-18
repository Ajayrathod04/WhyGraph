@echo off
REM One-click start for Windows. Requires Docker Desktop and Python 3.10+.
cd /d %~dp0
if not exist .venv (
  py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate
pip install -q -r requirements.txt
docker compose up -d
echo Waiting for FalkorDB...
timeout /t 4 /nobreak >nul
python -m whygraph
